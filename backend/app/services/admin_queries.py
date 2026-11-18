import uuid
from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta, timezone
from typing import Any, TypeVar, cast

from sqlalchemy import case, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.api.admin_deps import AdminScope
from app.core.config import settings
from app.core.errors import AppError
from app.core.time import as_utc, utcnow
from app.models.admin import AdminUser
from app.models.entities import Agent, AuditLog, Business, Card, PosKey, Transaction, User, UserCard
from app.schemas.admin import (
    AdminTransactionItem,
    AgentHealth,
    AgentHealthCounts,
    AgentItem,
    AuditItem,
    BusinessDetail,
    BusinessListItem,
    CardDetail,
    CardListItem,
    CardPage,
    DashboardResponse,
    Page,
    TransactionPage,
    UserDetail,
    UserListItem,
    UserSearchRequest,
)
from app.services.admin_mutations import safe_audit_snapshot
from app.services.admin_security import mask_phone, sanitize_agent_error

T = TypeVar("T")
ASTANA_TIMEZONE = timezone(timedelta(hours=5))

async def admin_identity(db: AsyncSession, admin: AdminUser) -> dict[str, Any]:
    business_data: dict[str, Any] | None = None
    if admin.business_id is not None:
        business = await db.scalar(select(Business).where(Business.id == admin.business_id))
        if business is None:
            raise AppError("ADMIN_UNAUTHENTICATED", "Admin authentication required", 401)
        business_data = {
            "id": business.id,
            "name": business.name,
            "status": business.status,
            "logo_url": business.logo_url,
            "android_app_id": business.android_app_id,
            "created_at": as_utc(business.created_at),
        }
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
        android_app_id=getattr(row, "android_app_id", None),
        status=row.status,
        loyalty_tiers=getattr(row, "loyalty_tiers", None),
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
        full_name=card.full_name,
        balance=f"{card.balance:.4f}",
        is_blocked=card.is_blocked,
        updated_at=as_utc(card.updated_at),
        bind_method=user_card.bind_method if user_card else None,
        bound_at=as_utc(user_card.bound_at) if user_card else None,
        hidden_at=as_utc(user_card.hidden_at) if user_card and user_card.hidden_at else None,
    )


def _transaction_item(row: Any) -> AdminTransactionItem:
    tx: Transaction = row[0]
    card: Card = row[1]
    business: Business = row[2]
    return AdminTransactionItem(
        id=tx.id,
        card_id=card.id,
        barcode=card.barcode,
        business_id=business.id,
        business_name=business.name,
        type=tx.type,
        amount=f"{tx.amount:.4f}",
        balance_after=f"{tx.balance_after:.4f}",
        occurred_at=as_utc(tx.occurred_at),
        receipt_ref=tx.receipt_ref,
        store=tx.store,
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


def _period_error(reason: str, message: str, **extra: Any) -> AppError:
    """Stable, localizable 422. `code` stays ADMIN_INVALID_PERIOD (old clients keep working);
    `reason` and the optional ISO-date bounds are the new machine-readable details."""
    return AppError("ADMIN_INVALID_PERIOD", message, 422, extra={"reason": reason, **extra})


def _validate_period(
    start: datetime | None,
    end: datetime | None,
    *,
    business_created_at: datetime | None = None,
    now: datetime | None = None,
) -> tuple[datetime, datetime, int]:
    """Calendar-day bounds in UTC+5: both dates end at today, inclusive.

    Registration affects the default start date only.
    No limit on the length of the period. An explicit bad range is never
    silently corrected; only a missing range is defaulted (and clamped to the business bounds)."""
    now_utc = as_utc(now) if now is not None else utcnow()
    today = now_utc.astimezone(ASTANA_TIMEZONE).date()
    min_day = as_utc(business_created_at).astimezone(ASTANA_TIMEZONE).date() if business_created_at else None
    bounds: dict[str, Any] = {"period_max": today.isoformat()}

    if start is not None and start.tzinfo is None:
        raise _period_error("PERIOD_TIMEZONE_REQUIRED", "Dates must include a timezone", **bounds)
    if end is not None and end.tzinfo is None:
        raise _period_error("PERIOD_TIMEZONE_REQUIRED", "Dates must include a timezone", **bounds)

    if end is not None:
        end_instant = as_utc(end)
        end_day = end_instant.astimezone(ASTANA_TIMEZONE).date()
    else:
        end_instant = now_utc
        end_day = today
    if start is not None:
        start_instant = as_utc(start)
        start_day = start_instant.astimezone(ASTANA_TIMEZONE).date()
    else:
        start_instant = None
        start_day = end_day - timedelta(days=30)
        if min_day is not None and start_day < min_day:
            start_day = min(min_day, end_day)  # new business opens at once, no silent fix of explicit input

    if end_day > today or start_day > today:
        raise _period_error(
            "PERIOD_AFTER_REPORT_DATE", "Period must not end after the report date", **bounds
        )
    if start_day > end_day or (start_instant is not None and end is not None and start_instant > end_instant):
        raise _period_error("PERIOD_START_AFTER_END", "Start date must not be after end date", **bounds)
    period_days = (end_day - start_day).days + 1
    start_utc = datetime.combine(start_day, time.min, ASTANA_TIMEZONE).astimezone(UTC)
    end_utc = datetime.combine(end_day, time.max, ASTANA_TIMEZONE).astimezone(UTC)
    return start_utc, end_utc, period_days


async def dashboard(
    db: AsyncSession,
    scope: AdminScope,
    business_id: uuid.UUID | None,
    start: datetime | None,
    end: datetime | None,
) -> DashboardResponse:
    business_filter = scope.business_id_for(business_id)
    registered_at: datetime | None = None
    if business_filter is not None:
        business = await db.scalar(select(Business).where(Business.id == business_filter))
        if business is None:
            raise AppError("ADMIN_RESOURCE_NOT_FOUND", "Resource not found", 404)
        business_name = business.name
        registered_at = business.created_at
    else:
        business_name = None
    start_utc, end_utc, period_days = _validate_period(
        start, end, business_created_at=registered_at, now=utcnow()
    )
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


async def _count_cards(db: AsyncSession, conditions: list[Any]) -> int:
    """Exact number of cards for the very same conditions as the page query.

    `user_cards.card_id` is UNIQUE, so the outer join of the page query never multiplies a card and counting
    `cards` joined to `businesses` gives the same set. Not a stable snapshot: it is read in its own statement.
    """
    stmt = (
        select(func.count(Card.id))
        .select_from(Card)
        .join(Business, Business.id == Card.business_id)
        .where(*conditions)
    )
    return int(await db.scalar(stmt) or 0)


def _card_page(rows: list[Any], limit: int, offset: int, total: int) -> CardPage:
    page = _page(rows, limit, offset, _card_item)
    return CardPage(**page.model_dump(), total=total)


async def list_cards(
    db: AsyncSession,
    scope: AdminScope,
    business_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> CardPage:
    conditions = [scope.predicate(Card.business_id, business_id)]
    query = (
        select(Card, Business, UserCard)
        .join(Business, Business.id == Card.business_id)
        .outerjoin(UserCard, UserCard.card_id == Card.id)
        .where(*conditions)
        .order_by(Card.updated_at.desc(), Card.id.desc())
        .limit(limit + 1)
        .offset(offset)
    )
    rows = (await db.execute(query)).all()
    return _card_page(list(rows), limit, offset, await _count_cards(db, conditions))


async def search_cards(
    db: AsyncSession,
    scope: AdminScope,
    barcode: str | None,
    phone: str | None,
    business_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> CardPage:
    from app.schemas.admin import CardSearchRequest

    # Re-apply the validated DTO even for service callers outside FastAPI.
    filters = CardSearchRequest(barcode=barcode, phone=phone, business_id=business_id)
    conditions: list[Any] = [scope.predicate(Card.business_id, filters.business_id)]
    match_clauses: list[Any] = []
    if filters.barcode is not None:
        match_clauses.append(Card.barcode == filters.barcode)
        match_clauses.append(Card.barcode.endswith(filters.barcode))
    if filters.phone is not None:
        match_clauses.append(Card.phone == filters.phone)
        match_clauses.append(Card.phone.endswith(filters.phone))
        if filters.phone.startswith("+7") and len(filters.phone) == 12:
            sub_digits = filters.phone[2:]
            match_clauses.append(Card.phone.endswith(sub_digits))
            match_clauses.append(Card.barcode.endswith(sub_digits))
    if match_clauses:
        conditions.append(or_(*match_clauses))
    query = (
        select(Card, Business, UserCard)
        .join(Business, Business.id == Card.business_id)
        .outerjoin(UserCard, UserCard.card_id == Card.id)
        .where(*conditions)
    )
    rows = (
        await db.execute(query.order_by(Card.updated_at.desc(), Card.id.desc()).limit(limit + 1).offset(offset))
    ).all()
    return _card_page(list(rows), limit, offset, await _count_cards(db, conditions))


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
    user: User | None = row[3]
    return CardDetail(
        **result,
        owner_language=user.language if user and user.deleted_at is None else None,
    )


async def list_card_transactions(
    db: AsyncSession,
    scope: AdminScope,
    card_id: uuid.UUID,
    limit: int,
    offset: int,
) -> TransactionPage:
    card_row = (
        await db.execute(
            select(Card, Business)
            .join(Business, Business.id == Card.business_id)
            .where(Card.id == card_id, scope.predicate(Card.business_id))
        )
    ).first()
    if card_row is None:
        raise AppError("ADMIN_RESOURCE_NOT_FOUND", "Resource not found", 404)
    card: Card = card_row[0]
    business: Business = card_row[1]
    tx_rows = (
        await db.scalars(
            select(Transaction)
            .where(Transaction.card_id == card.id)
            .order_by(Transaction.occurred_at.desc(), Transaction.id.desc())
            .limit(limit + 1)
            .offset(offset)
        )
    ).all()
    total = int(await db.scalar(select(func.count(Transaction.id)).where(Transaction.card_id == card.id)) or 0)
    page = _page(
        [(tx, card, business) for tx in tx_rows],
        limit,
        offset,
        _transaction_item,
    )
    return TransactionPage(**page.model_dump(), total=total)


async def list_users(
    db: AsyncSession,
    scope: AdminScope,
    business_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> Page[UserListItem]:
    resolved_business_id = scope.business_id_for(business_id)
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
        .where(UserCard.user_id == User.id, scope.predicate(Card.business_id, business_id))
        .scalar_subquery()
    )
    rows = (
        await db.execute(
            select(User, card_count)
            .where(User.deleted_at.is_(None), has_scoped_card)
            .order_by(User.created_at.desc(), User.id.desc())
            .limit(limit + 1)
            .offset(offset)
        )
    ).all()
    return _page(list(rows), limit, offset, _user_item)


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
            .where(
                or_(
                    User.phone == filters.phone,
                    User.phone.endswith(filters.phone),
                ),
                User.deleted_at.is_(None),
                has_scoped_card,
            )
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


async def list_user_transactions(
    db: AsyncSession,
    scope: AdminScope,
    user_id: uuid.UUID,
    business_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> TransactionPage:
    resolved_business_id = scope.business_id_for(business_id)
    scoped_card_ids = (
        select(Card.id)
        .join(UserCard, UserCard.card_id == Card.id)
        .where(scope.predicate(Card.business_id, resolved_business_id))
    )
    user = await db.scalar(
        select(User).where(
            User.id == user_id,
            User.deleted_at.is_(None),
            select(UserCard.id)
            .where(UserCard.user_id == User.id, UserCard.card_id.in_(scoped_card_ids))
            .exists(),
        )
    )
    if user is None:
        raise AppError("ADMIN_RESOURCE_NOT_FOUND", "Resource not found", 404)

    tx_conditions = [
        UserCard.user_id == user.id,
        scope.predicate(Card.business_id, business_id),
    ]
    rows = (
        await db.execute(
            select(Transaction, Card, Business)
            .join(Card, Card.id == Transaction.card_id)
            .join(UserCard, UserCard.card_id == Card.id)
            .join(Business, Business.id == Card.business_id)
            .where(*tx_conditions)
            .order_by(Transaction.occurred_at.desc(), Transaction.id.desc())
            .limit(limit + 1)
            .offset(offset)
        )
    ).all()
    total = int(
        await db.scalar(
            select(func.count(Transaction.id))
            .select_from(Transaction)
            .join(Card, Card.id == Transaction.card_id)
            .join(UserCard, UserCard.card_id == Card.id)
            .where(*tx_conditions)
        )
        or 0
    )
    page = _page(list(rows), limit, offset, _transaction_item)
    return TransactionPage(**page.model_dump(), total=total)


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
            before_state=safe_audit_snapshot(
                row.action,
                row.before_state,
                admin_user_id=row.admin_user_id,
                business_id=row.business_id,
            ),
            after_state=safe_audit_snapshot(
                row.action,
                row.after_state,
                admin_user_id=row.admin_user_id,
                business_id=row.business_id,
            ),
            created_at=as_utc(row.created_at),
        ),
    )


async def list_pos_keys(
    db: AsyncSession, scope: AdminScope, business_id: uuid.UUID
) -> list[PosKey]:
    scope.require_superadmin()
    business = await db.scalar(select(Business).where(Business.id == business_id))
    if business is None:
        raise AppError("ADMIN_RESOURCE_NOT_FOUND", "Resource not found", 404)
    stmt = (
        select(PosKey)
        .where(PosKey.business_id == business_id)
        .order_by(PosKey.created_at.desc())
    )
    return list((await db.scalars(stmt)).all())
