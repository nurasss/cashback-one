import uuid
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, TypeVar, cast

from sqlalchemy import case, func, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.api.admin_deps import AdminScope
from app.core.config import settings
from app.core.errors import AppError
from app.core.time import as_utc, utcnow
from app.models.admin import AdminUser
from app.models.entities import Agent, AuditLog, Business, Card, Transaction, User, UserCard
from app.schemas.admin import (
    AgentHealth,
    AgentHealthCounts,
    AgentItem,
    AuditItem,
    BusinessDetail,
    BusinessListItem,
    CardDetail,
    CardListItem,
    DashboardResponse,
    Page,
    UserDetail,
    UserListItem,
    UserSearchRequest,
)
from app.services.admin_mutations import sanitize_admin_audit_state
from app.services.admin_security import mask_phone, sanitize_agent_error

T = TypeVar("T")

async def admin_identity(db: AsyncSession, admin: AdminUser) -> dict[str, Any]:
    business_data: dict[str, Any] | None = None
    if admin.business_id is not None:
        business = await db.scalar(select(Business).where(Business.id == admin.business_id))
        if business is None:
            raise AppError("ADMIN_UNAUTHENTICATED", "Admin authentication required", 401)
        business_data = {"id": business.id, "name": business.name, "status": business.status}
    return {
        "id": admin.id,
        "login": admin.login,
        "role": admin.role,
        "business": business_data,
    }


def _page(rows: list[Any], limit: int, offset: int, convert: Callable[[Any], T]) -> Page[T]:
    has_more = len(rows) > limit
    return Page[T](
        items=[convert(row) for row in rows[:limit]],
        limit=limit,
        offset=offset,
        has_more=has_more,
    )


def _business_item(row: Business) -> BusinessListItem:
    return BusinessListItem(
        id=row.id,
        name=row.name,
        logo_url=row.logo_url,
        colors=row.colors,
        barcode_prefixes=row.barcode_prefixes,
        status=row.status,
        created_at=as_utc(row.created_at),
        updated_at=as_utc(row.updated_at),
    )


def _agent_health_expr(now: datetime) -> ColumnElement[str]:
    stale_before = now - timedelta(seconds=settings.admin_agent_stale_seconds)
    return case(
        (Agent.status != "active", "disabled"),
        ((Agent.last_error.is_not(None)) & (Agent.last_error != ""), "error"),
        (Agent.last_seen_at.is_(None), "never_connected"),
        (Agent.last_seen_at < stale_before, "stale"),
        else_="online",
    )


def _agent_item(row: Any, health: str) -> AgentItem:
    agent: Agent = row[0]
    business: Business = row[1]
    return AgentItem(
        id=agent.id,
        business_id=agent.business_id,
        business_name=business.name,
        status=agent.status,
        health=cast(AgentHealth, health),  # SQL CASE emits the documented health enum.
        last_seen_at=as_utc(agent.last_seen_at) if agent.last_seen_at else None,
        version=agent.version,
        last_sync_at=as_utc(agent.last_sync_at) if agent.last_sync_at else None,
        last_error=sanitize_agent_error(agent.last_error),
        created_at=as_utc(agent.created_at),
    )


def _card_item(row: Any) -> CardListItem:
    card: Card = row[0]
    business: Business = row[1]
    user_card: UserCard | None = row[2]
    return CardListItem(
        id=card.id,
        business_id=card.business_id,
        business_name=business.name,
        barcode=card.barcode,
        phone_masked=mask_phone(card.phone),
        balance=f"{card.balance:.4f}",
        is_blocked=card.is_blocked,
        updated_at=as_utc(card.updated_at),
        bind_method=user_card.bind_method if user_card else None,
        bound_at=as_utc(user_card.bound_at) if user_card else None,
        hidden_at=as_utc(user_card.hidden_at) if user_card and user_card.hidden_at else None,
    )


def _user_item(row: Any) -> UserListItem:
    user: User = row[0]
    return UserListItem(
        id=user.id,
        phone_masked=mask_phone(user.phone),
        language=user.language,
        created_at=as_utc(user.created_at),
        business_cards_count=int(row[1]),
    )


def _validate_period(start: datetime | None, end: datetime | None) -> tuple[datetime, datetime, int]:
    end_utc = as_utc(end) if end is not None else utcnow()
    start_utc = as_utc(start) if start is not None else end_utc - timedelta(days=30)
    if start is not None and start.tzinfo is None:
        raise AppError("ADMIN_INVALID_PERIOD", "Dates must include a timezone", 422)
    if end is not None and end.tzinfo is None:
        raise AppError("ADMIN_INVALID_PERIOD", "Dates must include a timezone", 422)
    if start_utc > end_utc:
        raise AppError("ADMIN_INVALID_PERIOD", "Start date must not be after end date", 422)
    seconds = (end_utc - start_utc).total_seconds()
    if seconds > settings.admin_max_stats_period_days * 86400:
        raise AppError(
            "ADMIN_PERIOD_TOO_LARGE",
            f"Choose a period of {settings.admin_max_stats_period_days} days or less",
            422,
        )
    return start_utc, end_utc, max(1, (int(seconds) + 86399) // 86400)


async def dashboard(
    db: AsyncSession,
    scope: AdminScope,
    business_id: uuid.UUID | None,
    start: datetime | None,
    end: datetime | None,
) -> DashboardResponse:
    start_utc, end_utc, period_days = _validate_period(start, end)
    business_filter = scope.business_id_for(business_id)
    if business_filter is not None:
        business = await db.scalar(select(Business).where(Business.id == business_filter))
        if business is None:
            raise AppError("ADMIN_RESOURCE_NOT_FOUND", "Resource not found", 404)
        business_name = business.name
    else:
        business_name = None
    business_predicate = (
        Card.business_id == business_filter if business_filter is not None else true()
    )

    customer_count = await db.scalar(
        select(func.count(func.distinct(User.id)))
        .select_from(User)
        .join(UserCard, UserCard.user_id == User.id)
        .join(Card, Card.id == UserCard.card_id)
        .where(User.deleted_at.is_(None), business_predicate)
    )
    card_counts = (
        await db.execute(
            select(
                func.count(Card.id),
                func.count(case((Card.is_blocked.is_(False), Card.id))),
            ).where(business_predicate)
        )
    ).one()
    transaction_count = await db.scalar(
        select(func.count(Transaction.id))
        .select_from(Transaction)
        .join(Card, Card.id == Transaction.card_id)
        .where(
            business_predicate,
            Transaction.occurred_at >= start_utc,
            Transaction.occurred_at <= end_utc,
        )
    )
    now = utcnow()
    health_expr = _agent_health_expr(now)
    health_rows = (
        await db.execute(
            select(health_expr, func.count(Agent.id))
            .join(Business, Business.id == Agent.business_id)
            .where(Business.id == business_filter if business_filter is not None else true())
            .group_by(health_expr)
        )
    ).all()
    health = {row[0]: int(row[1]) for row in health_rows}
    return DashboardResponse(
        business_id=business_filter,
        business_name=business_name,
        period_from=start_utc,
        period_to=end_utc,
        period_days=period_days,
        customers_with_business_cards=int(customer_count or 0),
        cards=int(card_counts[0] or 0),
        unblocked_cards=int(card_counts[1] or 0),
        transactions=int(transaction_count or 0),
        agents=AgentHealthCounts(**{key: health.get(key, 0) for key in AgentHealthCounts.model_fields}),
    )


async def list_businesses(db: AsyncSession, limit: int, offset: int) -> Page[BusinessListItem]:
    rows = (
        await db.scalars(
            select(Business)
            .order_by(Business.updated_at.desc(), Business.id.desc())
            .limit(limit + 1)
            .offset(offset)
        )
    ).all()
    return _page(list(rows), limit, offset, _business_item)


async def get_business(db: AsyncSession, business_id: uuid.UUID) -> BusinessDetail:
    business = await db.scalar(select(Business).where(Business.id == business_id))
    if business is None:
        raise AppError("ADMIN_RESOURCE_NOT_FOUND", "Resource not found", 404)
    cards, unblocked = (
        await db.execute(
            select(
                func.count(Card.id),
                func.count(case((Card.is_blocked.is_(False), Card.id))),
            ).where(Card.business_id == business_id)
        )
    ).one()
    customers = await db.scalar(
        select(func.count(func.distinct(UserCard.user_id)))
        .select_from(UserCard)
        .join(Card, Card.id == UserCard.card_id)
        .join(User, User.id == UserCard.user_id)
        .where(Card.business_id == business_id, User.deleted_at.is_(None))
    )
    agents = await db.scalar(select(func.count(Agent.id)).where(Agent.business_id == business_id))
    return BusinessDetail(
        **_business_item(business).model_dump(),
        cards_count=int(cards or 0),
        unblocked_cards_count=int(unblocked or 0),
        customers_with_cards_count=int(customers or 0),
        agents_count=int(agents or 0),
    )


async def list_agents(
    db: AsyncSession, scope: AdminScope, business_id: uuid.UUID | None, limit: int, offset: int
) -> Page[AgentItem]:
    health_expr = _agent_health_expr(utcnow())
    rows = (
        await db.execute(
            select(Agent, Business, health_expr)
            .join(Business, Business.id == Agent.business_id)
            .where(scope.predicate(Agent.business_id, business_id))
            .order_by(Agent.created_at.desc(), Agent.id.desc())
            .limit(limit + 1)
            .offset(offset)
        )
    ).all()
    return _page(list(rows), limit, offset, lambda row: _agent_item((row[0], row[1]), row[2]))


async def get_agent(
    db: AsyncSession, scope: AdminScope, agent_id: uuid.UUID
) -> AgentItem:
    health_expr = _agent_health_expr(utcnow())
    row = (
        await db.execute(
            select(Agent, Business, health_expr)
            .join(Business, Business.id == Agent.business_id)
            .where(Agent.id == agent_id, scope.predicate(Agent.business_id))
        )
    ).first()
    if row is None:
        raise AppError("ADMIN_RESOURCE_NOT_FOUND", "Resource not found", 404)
    return _agent_item((row[0], row[1]), row[2])


async def search_cards(
    db: AsyncSession,
    scope: AdminScope,
    barcode: str | None,
    phone: str | None,
    business_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> Page[CardListItem]:
    from app.schemas.admin import CardSearchRequest

    # Re-apply the validated DTO even for service callers outside FastAPI.
    filters = CardSearchRequest(barcode=barcode, phone=phone, business_id=business_id)
    query = (
        select(Card, Business, UserCard)
        .join(Business, Business.id == Card.business_id)
        .outerjoin(UserCard, UserCard.card_id == Card.id)
        .where(scope.predicate(Card.business_id, filters.business_id))
    )
    if filters.barcode is not None:
        query = query.where(Card.barcode == filters.barcode)
    if filters.phone is not None:
        query = query.where(Card.phone == filters.phone)
    rows = (
        await db.execute(query.order_by(Card.updated_at.desc(), Card.id.desc()).limit(limit + 1).offset(offset))
    ).all()
    return _page(list(rows), limit, offset, _card_item)


async def get_card_detail(
    db: AsyncSession, scope: AdminScope, card_id: uuid.UUID
) -> CardDetail:
    row = (
        await db.execute(
            select(Card, Business, UserCard, User)
            .join(Business, Business.id == Card.business_id)
            .outerjoin(UserCard, UserCard.card_id == Card.id)
            .outerjoin(User, User.id == UserCard.user_id)
            .where(Card.id == card_id, scope.predicate(Card.business_id))
        )
    ).first()
    if row is None:
        raise AppError("ADMIN_RESOURCE_NOT_FOUND", "Resource not found", 404)
    result = _card_item((row[0], row[1], row[2])).model_dump()
    card: Card = row[0]
    user: User | None = row[3]
    return CardDetail(
        **result,
        full_name=card.full_name,
        owner_language=user.language if user and user.deleted_at is None else None,
    )


async def search_users(
    db: AsyncSession,
    scope: AdminScope,
    phone: str,
    business_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> Page[UserListItem]:
    filters = UserSearchRequest(phone=phone, business_id=business_id)
    resolved_business_id = scope.business_id_for(filters.business_id)
    scoped_card_ids = (
        select(Card.id)
        .select_from(Card)
        .join(UserCard, UserCard.card_id == Card.id)
        .where(scope.predicate(Card.business_id, resolved_business_id))
    )
    has_scoped_card = (
        select(UserCard.id)
        .where(UserCard.user_id == User.id, UserCard.card_id.in_(scoped_card_ids))
        .exists()
    )
    card_count = (
        select(func.count(Card.id))
        .select_from(Card)
        .join(UserCard, UserCard.card_id == Card.id)
        .where(UserCard.user_id == User.id, scope.predicate(Card.business_id, filters.business_id))
        .scalar_subquery()
    )
    rows = (
        await db.execute(
            select(User, card_count)
            .where(User.phone == filters.phone, User.deleted_at.is_(None), has_scoped_card)
            .order_by(User.created_at.desc(), User.id.desc())
            .limit(limit + 1)
            .offset(offset)
        )
    ).all()
    return _page(list(rows), limit, offset, _user_item)


async def get_user_detail(
    db: AsyncSession,
    scope: AdminScope,
    user_id: uuid.UUID,
    business_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> UserDetail:
    resolved_business_id = scope.business_id_for(business_id)
    scoped_card_ids = (
        select(Card.id)
        .join(UserCard, UserCard.card_id == Card.id)
        .where(scope.predicate(Card.business_id, resolved_business_id))
    )
    user = await db.scalar(
        select(User)
        .where(
            User.id == user_id,
            User.deleted_at.is_(None),
            select(UserCard.id)
            .where(UserCard.user_id == User.id, UserCard.card_id.in_(scoped_card_ids))
            .exists(),
        )
    )
    if user is None:
        raise AppError("ADMIN_RESOURCE_NOT_FOUND", "Resource not found", 404)

    card_query = (
        select(Card, Business, UserCard)
        .join(UserCard, UserCard.card_id == Card.id)
        .join(Business, Business.id == Card.business_id)
        .where(
            UserCard.user_id == user.id,
            scope.predicate(Card.business_id, business_id),
        )
    )
    rows = (
        await db.execute(
            card_query.order_by(UserCard.bound_at.desc(), Card.id.desc()).limit(limit + 1).offset(offset)
        )
    ).all()
    page = _page(list(rows), limit, offset, _card_item)
    return UserDetail(
        id=user.id,
        phone=user.phone,
        language=user.language,
        created_at=as_utc(user.created_at),
        cards=page,
    )


async def list_audit_logs(
    db: AsyncSession, scope: AdminScope, limit: int, offset: int
) -> Page[AuditItem]:
    statement = select(AuditLog)
    if scope.role == "business_manager":
        # Legacy audit entries have no business_id and are intentionally invisible to managers.
        statement = statement.where(AuditLog.business_id == scope.business_id)
    rows = (
        await db.scalars(
            statement
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(limit + 1)
            .offset(offset)
        )
    ).all()
    return _page(
        list(rows),
        limit,
        offset,
        lambda row: AuditItem(
            id=row.id,
            actor=row.actor,
            admin_user_id=row.admin_user_id,
            business_id=row.business_id,
            action=row.action,
            entity=row.entity,
            before_state=sanitize_admin_audit_state(row.before_state),
            after_state=sanitize_admin_audit_state(row.after_state),
            created_at=as_utc(row.created_at),
        ),
    )
