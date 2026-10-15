"""Wallet service for customer cards, auto-binding, and transaction history."""
import base64
import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
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
    cards_stmt = (
        select(Card.id)
        .join(Business, Business.id == Card.business_id)
        .where(Card.phone == clean_phone, Business.status == "active")
    )
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
                "Auto-bind skipped because candidate card %s already has an owner",
                row.card_id,
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
            Business.status == "active",
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
                updated_at=card.updated_at,
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
            Business.status == "active",
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
        updated_at=card.updated_at,
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
    """Soft-hide card from user wallet by atomically setting hidden_at timestamp."""
    now = utcnow()
    stmt = (
        update(UserCard)
        .where(
            UserCard.user_id == user_id,
            UserCard.card_id == card_id,
            UserCard.hidden_at.is_(None),
        )
        .values(hidden_at=now)
        .returning(UserCard.id)
    )
    result = await session.execute(stmt)
    updated_id = result.scalar_one_or_none()
    if not updated_id:
        raise AppError(
            code="CARD_NOT_FOUND",
            message="Card not found in your wallet",
            status_code=404,
        )
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
    ownership_stmt = (
        select(UserCard.id)
        .join(Card, Card.id == UserCard.card_id)
        .join(Business, Business.id == Card.business_id)
        .where(
            UserCard.user_id == user_id,
            UserCard.card_id == card_id,
            UserCard.hidden_at.is_(None),
            Business.status == "active",
        )
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


def resolve_candidate_card(
    candidates: list[tuple[Card, Business]],
    barcode: str,
) -> tuple[Card, Business]:
    """Resolve a single candidate Card and Business from matching candidates.

    If multiple candidates exist, filters by Business.barcode_prefixes.
    If resolution is ambiguous or yields no match, raises AppError(BUSINESS_SELECTION_REQUIRED).
    """
    if len(candidates) == 1:
        return candidates[0]

    # Filter candidates by prefixes
    prefix_matched: list[tuple[Card, Business]] = []
    for card, business in candidates:
        prefixes = business.barcode_prefixes
        if prefixes and isinstance(prefixes, list):
            for prefix in prefixes:
                if isinstance(prefix, str) and prefix and barcode.startswith(prefix):
                    prefix_matched.append((card, business))
                    break

    if len(prefix_matched) == 1:
        return prefix_matched[0]

    # Ambiguous or no prefix match: construct safe candidate business list
    seen_ids: set[uuid.UUID] = set()
    businesses_list: list[dict[str, Any]] = []
    for _, business in candidates:
        if business.id not in seen_ids:
            seen_ids.add(business.id)
            businesses_list.append(
                {
                    "id": str(business.id),
                    "name": business.name,
                    "logo_url": business.logo_url,
                    "colors": business.colors or {},
                }
            )
    businesses_list.sort(key=lambda b: b["name"])

    raise AppError(
        code="BUSINESS_SELECTION_REQUIRED",
        message="Select the business for this loyalty card.",
        status_code=409,
        extra={"businesses": businesses_list},
    )


async def bind_customer_card(
    session: AsyncSession,
    user: User,
    barcode: str,
    business_id: uuid.UUID | None = None,
) -> CustomerCardResponse:
    """Manually bind an existing loyalty card via barcode or scanned QR.

    Steps & Invariants:
    1. Card lookup: Looks up existing Card in mirror for active businesses.
       - If business_id provided: matches Card.business_id == business_id and Card.barcode == barcode.
       - If business_id omitted: finds all active candidates, resolves via barcode_prefixes,
         or raises BUSINESS_SELECTION_REQUIRED.
       - If no candidate found: raises CARD_NOT_FOUND (404).
    2. Phone ownership check:
       - If card.phone IS NULL: raises CARD_ACTIVATION_REQUIRED (409).
       - If card.phone has invalid format: raises CARD_BIND_NOT_ALLOWED (409).
       - If normalize(card.phone) != current_user.phone: raises CARD_BIND_NOT_ALLOWED (409).
       - No PII is logged or leaked.
    3. Existing ownership & concurrency:
       - If card already bound to another user: raises CARD_BIND_NOT_ALLOWED (409).
       - If card already bound to current user:
         * If hidden: unhides it (hidden_at = None) and preserves initial bound_at & bind_method.
         * If visible: idempotent return.
       - If unbound: inserts UserCard with bind_method="manual_barcode".
       - Invariant uq_user_cards_card_id enforced; concurrency-safe on PostgreSQL and SQLite.
    4. Blocked card:
       - is_blocked=True does NOT prevent linking; card is returned with is_blocked=True.
       - Card mirror attributes (balance, updated_at, etc.) are never modified.
    """
    clean_barcode = barcode.strip()

    # 1. Query candidate cards in active businesses
    query = (
        select(Card, Business)
        .join(Business, Business.id == Card.business_id)
        .where(
            Card.barcode == clean_barcode,
            Business.status == "active",
        )
    )
    if business_id is not None:
        query = query.where(Card.business_id == business_id)

    raw_candidates = list((await session.execute(query)).all())
    if not raw_candidates:
        raise AppError(
            code="CARD_NOT_FOUND",
            message="Card not found",
            status_code=404,
        )

    candidates: list[tuple[Card, Business]] = [(r[0], r[1]) for r in raw_candidates]
    target_card, target_business = resolve_candidate_card(candidates, clean_barcode)

    # 2. Phone ownership check
    if not target_card.phone:
        raise AppError(
            code="CARD_ACTIVATION_REQUIRED",
            message="This card requires activation before it can be linked.",
            status_code=409,
        )

    try:
        normalized_card_phone = normalize_phone(target_card.phone)
    except ValueError:
        logger.warning(
            "Card %s has unparseable phone format, manual bind rejected",
            target_card.id,
        )
        raise AppError(
            code="CARD_BIND_NOT_ALLOWED",
            message="This card cannot be linked to the current account.",
            status_code=409,
        )

    if not user.phone:
        raise AppError(
            code="CARD_BIND_NOT_ALLOWED",
            message="This card cannot be linked to the current account.",
            status_code=409,
        )

    try:
        normalized_user_phone = normalize_phone(user.phone)
    except ValueError:
        raise AppError(
            code="CARD_BIND_NOT_ALLOWED",
            message="This card cannot be linked to the current account.",
            status_code=409,
        )

    if normalized_card_phone != normalized_user_phone:
        logger.info("Manual bind rejected due to phone mismatch for card %s", target_card.id)
        raise AppError(
            code="CARD_BIND_NOT_ALLOWED",
            message="This card cannot be linked to the current account.",
            status_code=409,
        )

    # 3. Ownership and binding
    uc_stmt = select(UserCard).where(UserCard.card_id == target_card.id)
    existing_uc = (await session.execute(uc_stmt)).scalar_one_or_none()
    final_uc: UserCard

    if existing_uc is not None:
        if existing_uc.user_id != user.id:
            logger.info("Manual bind rejected: card %s already owned by another user", target_card.id)
            raise AppError(
                code="CARD_BIND_NOT_ALLOWED",
                message="This card cannot be linked to the current account.",
                status_code=409,
            )

        # Same user: if hidden, unhide it!
        if existing_uc.hidden_at is not None:
            await session.execute(
                update(UserCard)
                .where(
                    UserCard.card_id == target_card.id,
                    UserCard.user_id == user.id,
                    UserCard.hidden_at.is_not(None),
                )
                .values(hidden_at=None)
            )
            await session.commit()
            existing_uc.hidden_at = None
        final_uc = existing_uc
    else:
        # Not yet bound: insert new UserCard
        now = utcnow()
        new_id = uuid.uuid4()
        dialect = session.bind.dialect.name if session.bind else ""
        if dialect == "postgresql":
            stmt = (
                pg_insert(UserCard)
                .values(
                    id=new_id,
                    user_id=user.id,
                    card_id=target_card.id,
                    bound_at=now,
                    bind_method="manual_barcode",
                    hidden_at=None,
                )
                .on_conflict_do_nothing(index_elements=["card_id"])
            )
            await session.execute(stmt)
            await session.commit()
        else:
            try:
                new_uc = UserCard(
                    id=new_id,
                    user_id=user.id,
                    card_id=target_card.id,
                    bound_at=now,
                    bind_method="manual_barcode",
                    hidden_at=None,
                )
                session.add(new_uc)
                await session.commit()
            except IntegrityError:
                await session.rollback()

        # Re-fetch after concurrent insert attempt
        final_uc_stmt = select(UserCard).where(UserCard.card_id == target_card.id)
        fetched_uc = (await session.execute(final_uc_stmt)).scalar_one_or_none()
        if fetched_uc is None:
            raise AppError(
                code="CARD_BIND_NOT_ALLOWED",
                message="This card cannot be linked to the current account.",
                status_code=409,
            )

        if fetched_uc.user_id != user.id:
            logger.info("Manual bind rejected: card %s claimed by concurrent owner", target_card.id)
            raise AppError(
                code="CARD_BIND_NOT_ALLOWED",
                message="This card cannot be linked to the current account.",
                status_code=409,
            )

        if fetched_uc.hidden_at is not None:
            await session.execute(
                update(UserCard)
                .where(
                    UserCard.card_id == target_card.id,
                    UserCard.user_id == user.id,
                    UserCard.hidden_at.is_not(None),
                )
                .values(hidden_at=None)
            )
            await session.commit()
            fetched_uc.hidden_at = None
        final_uc = fetched_uc

    branding_obj = extract_branding(target_business)
    return CustomerCardResponse(
        id=target_card.id,
        barcode=target_card.barcode,
        balance=target_card.balance,
        is_blocked=target_card.is_blocked,
        updated_at=target_card.updated_at,
        bound_at=final_uc.bound_at,
        bind_method=final_uc.bind_method,
        business=BusinessInfo(
            id=target_business.id,
            name=target_business.name,
            branding=branding_obj,
        ),
    )
