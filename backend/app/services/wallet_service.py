"""Wallet service for customer cards, auto-binding, and transaction history."""
import base64
import logging
import uuid
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.phone import normalize_phone
from app.core.time import as_utc, utcnow
from app.models.entities import Business, Card, Transaction, User, UserCard
from app.schemas.wallet import (
    BusinessBranding,
    BusinessInfo,
    CustomerCardResponse,
    CustomerTransactionHistoryResponse,
    CustomerTransactionResponse,
)

logger = logging.getLogger(__name__)


def encode_cursor(occurred_at: datetime, tx_id: uuid.UUID) -> str:
    """Encode deterministic keyset cursor (occurred_at, id) to base64."""
    utc_dt = as_utc(occurred_at)
    payload = f"{utc_dt.isoformat()}|{tx_id}"
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("utf-8")


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    """Decode base64 cursor to (occurred_at, id)."""
    try:
        raw = base64.urlsafe_b64decode(cursor.strip().encode("utf-8")).decode("utf-8")
        dt_str, id_str = raw.split("|", 1)
        dt = as_utc(datetime.fromisoformat(dt_str))
        tx_id = uuid.UUID(id_str)
        return dt, tx_id
    except Exception as err:
        raise AppError(
            code="INVALID_CURSOR",
            message="Invalid pagination cursor format",
            status_code=400,
        ) from err


async def auto_bind_cards_by_phone(
    session: AsyncSession,
    user: User,
) -> list[uuid.UUID]:
    """Find unlinked cards matching the verified user phone and link them to user.

    Invariants & Protections:
    1. Only matches cards with phone == user.phone (normalized).
    2. If a card is already bound to this user (visible or hidden), it is skipped.
       Crucially: a previously hidden card is NOT automatically unhidden.
    3. If a card is already bound to another user, it is skipped (no card hijacking).
    4. Concurrency safe on PostgreSQL via ON CONFLICT DO NOTHING on card_id.
    """
    if not user.phone:
        return []

    try:
        clean_phone = normalize_phone(user.phone)
    except ValueError:
        return []

    # Find cards matching customer's phone
    cards_stmt = select(Card.id).where(Card.phone == clean_phone)
    candidate_card_ids = (await session.execute(cards_stmt)).scalars().all()
    if not candidate_card_ids:
        return []

    # Check existing bindings for candidate cards
    existing_stmt = select(UserCard.card_id, UserCard.user_id).where(
        UserCard.card_id.in_(candidate_card_ids)
    )
    existing_bindings = (await session.execute(existing_stmt)).all()
    bound_card_ids = {row.card_id for row in existing_bindings}

    for row in existing_bindings:
        if row.user_id != user.id:
            logger.warning(
                "Card %s matches phone %s of user %s but is already bound to user %s",
                row.card_id,
                clean_phone,
                user.id,
                row.user_id,
            )

    unbound_card_ids = [cid for cid in candidate_card_ids if cid not in bound_card_ids]
    if not unbound_card_ids:
        return []

    bind_time = utcnow()
    bound_ids: list[uuid.UUID] = []

    bind_name = session.bind.dialect.name if session.bind else ""
    if bind_name == "postgresql":
        for cid in unbound_card_ids:
            new_id = uuid.uuid4()
            stmt = (
                pg_insert(UserCard)
                .values(
                    id=new_id,
                    user_id=user.id,
                    card_id=cid,
                    bound_at=bind_time,
                    bind_method="phone_auto",
                    hidden_at=None,
                )
                .on_conflict_do_nothing(index_elements=["card_id"])
            )
            res = await session.execute(stmt)
            rowcount = getattr(res, "rowcount", None)
            if rowcount is not None and rowcount > 0:
                bound_ids.append(cid)
    else:
        for cid in unbound_card_ids:
            new_binding = UserCard(
                user_id=user.id,
                card_id=cid,
                bound_at=bind_time,
                bind_method="phone_auto",
                hidden_at=None,
            )
            session.add(new_binding)
            bound_ids.append(cid)

    await session.flush()
    return bound_ids


def extract_branding(business: Business) -> BusinessBranding:
    """Construct BusinessBranding from business logo_url and colors JSON."""
    colors = business.colors or {}
    primary = colors.get("primary_color") or colors.get("primary")
    accent = colors.get("accent_color") or colors.get("accent")
    return BusinessBranding(
        logo_url=business.logo_url,
        primary_color=primary,
        accent_color=accent,
    )


async def get_customer_cards(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> list[CustomerCardResponse]:
    """Retrieve all active (unhidden) cards belonging to the customer."""
    stmt = (
        select(Card, UserCard.bound_at, UserCard.bind_method, Business)
        .join(UserCard, UserCard.card_id == Card.id)
        .join(Business, Business.id == Card.business_id)
        .where(
            UserCard.user_id == user_id,
            UserCard.hidden_at.is_(None),
        )
        .order_by(UserCard.bound_at.desc(), Card.id.desc())
    )
    rows = (await session.execute(stmt)).all()

    cards: list[CustomerCardResponse] = []
    for card, bound_at, bind_method, business in rows:
        branding_obj = extract_branding(business)
        cards.append(
            CustomerCardResponse(
                id=card.id,
                barcode=card.barcode,
                balance=card.balance,
                is_blocked=card.is_blocked,
                bound_at=bound_at,
                bind_method=bind_method,
                business=BusinessInfo(
                    id=business.id,
                    name=business.name,
                    branding=branding_obj,
                ),
            )
        )
    return cards


async def get_customer_card_detail(
    session: AsyncSession,
    user_id: uuid.UUID,
    card_id: uuid.UUID,
) -> CustomerCardResponse:
    """Retrieve a single active card owned by customer, or 404 if not owned/hidden."""
    stmt = (
        select(Card, UserCard.bound_at, UserCard.bind_method, Business)
        .join(UserCard, UserCard.card_id == Card.id)
        .join(Business, Business.id == Card.business_id)
        .where(
            UserCard.user_id == user_id,
            UserCard.card_id == card_id,
            UserCard.hidden_at.is_(None),
        )
    )
    row = (await session.execute(stmt)).first()
    if not row:
        raise AppError(
            code="CARD_NOT_FOUND",
            message="Card not found in your wallet",
            status_code=404,
        )

    card, bound_at, bind_method, business = row
    branding_obj = extract_branding(business)
    return CustomerCardResponse(
        id=card.id,
        barcode=card.barcode,
        balance=card.balance,
        is_blocked=card.is_blocked,
        bound_at=bound_at,
        bind_method=bind_method,
        business=BusinessInfo(
            id=business.id,
            name=business.name,
            branding=branding_obj,
        ),
    )


async def hide_customer_card(
    session: AsyncSession,
    user_id: uuid.UUID,
    card_id: uuid.UUID,
) -> None:
    """Soft-hide card from user wallet by setting hidden_at timestamp."""
    stmt = select(UserCard).where(
        UserCard.user_id == user_id,
        UserCard.card_id == card_id,
        UserCard.hidden_at.is_(None),
    )
    user_card = (await session.execute(stmt)).scalar_one_or_none()
    if not user_card:
        raise AppError(
            code="CARD_NOT_FOUND",
            message="Card not found in your wallet",
            status_code=404,
        )

    user_card.hidden_at = utcnow()
    await session.commit()


async def get_customer_card_transactions(
    session: AsyncSession,
    user_id: uuid.UUID,
    card_id: uuid.UUID,
    limit: int = 20,
    cursor: str | None = None,
    tx_type: str | None = None,
) -> CustomerTransactionHistoryResponse:
    """Fetch cursor-paginated transaction history for a card owned by user."""
    # Enforce ownership and visibility check
    ownership_stmt = select(UserCard.id).where(
        UserCard.user_id == user_id,
        UserCard.card_id == card_id,
        UserCard.hidden_at.is_(None),
    )
    is_owned = (await session.execute(ownership_stmt)).scalar_one_or_none()
    if not is_owned:
        raise AppError(
            code="CARD_NOT_FOUND",
            message="Card not found in your wallet",
            status_code=404,
        )

    # Validate pagination limit
    if limit < 1 or limit > 100:
        raise AppError(
            code="INVALID_LIMIT",
            message="Pagination limit must be between 1 and 100",
            status_code=422,
        )

    stmt = select(Transaction).where(Transaction.card_id == card_id)

    if tx_type:
        stmt = stmt.where(Transaction.type == tx_type)

    if cursor:
        cursor_dt, cursor_id = decode_cursor(cursor)
        stmt = stmt.where(
            or_(
                Transaction.occurred_at < cursor_dt,
                and_(
                    Transaction.occurred_at == cursor_dt,
                    Transaction.id < cursor_id,
                ),
            )
        )

    stmt = stmt.order_by(Transaction.occurred_at.desc(), Transaction.id.desc()).limit(
        limit + 1
    )
    rows = list((await session.execute(stmt)).scalars().all())

    has_more = len(rows) > limit
    items = rows[:limit] if has_more else rows

    next_cursor = None
    if has_more and items:
        next_cursor = encode_cursor(items[-1].occurred_at, items[-1].id)

    return CustomerTransactionHistoryResponse(
        items=[CustomerTransactionResponse.model_validate(t) for t in items],
        next_cursor=next_cursor,
        has_more=has_more,
    )
