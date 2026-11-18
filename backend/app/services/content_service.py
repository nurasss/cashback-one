"""Customer-facing content: promotions, notifications and the "new" badges."""
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import Uuid, and_, exists, func, literal, or_, select, true
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement

from app.core.time import as_utc, utcnow
from app.models.entities import (
    Business,
    Card,
    Notification,
    NotificationRead,
    Promotion,
    RedemptionCode,
    User,
    UserCard,
)
from app.schemas.customer_app import (
    BadgesResponse,
    NotificationItem,
    NotificationMarkReadResponse,
    NotificationsResponse,
    PromotionItem,
    PromotionsResponse,
)

NOTIFICATIONS_PAGE_LIMIT = 100
# Only fresh movements notify the customer; history imported on first sync stays silent.
TRANSACTION_NOTIFY_WINDOW = timedelta(hours=24)


async def customer_business_ids(session: AsyncSession, user_id: uuid.UUID) -> list[uuid.UUID]:
    """Active businesses where the customer has a visible card."""
    stmt = (
        select(Card.business_id)
        .join(UserCard, UserCard.card_id == Card.id)
        .join(Business, Business.id == Card.business_id)
        .where(
            UserCard.user_id == user_id,
            UserCard.hidden_at.is_(None),
            Business.status == "active",
        )
        .distinct()
    )
    return list((await session.execute(stmt)).scalars().all())


def _audience(
    column: InstrumentedAttribute[uuid.UUID | None], business_ids: list[uuid.UUID]) -> ColumnElement[bool]:
    if business_ids:
        return or_(column.is_(None), column.in_(business_ids))
    return column.is_(None)


def _is_new(created_at: datetime, seen_at: datetime | None) -> bool:
    return seen_at is None or as_utc(created_at) > as_utc(seen_at)


def _visible_promotions(business_ids: list[uuid.UUID], now: datetime) -> ColumnElement[bool]:
    return and_(
        Promotion.is_active.is_(True),
        or_(Promotion.starts_at.is_(None), Promotion.starts_at <= now),
        or_(Promotion.ends_at.is_(None), Promotion.ends_at > now),
        _audience(Promotion.business_id, business_ids),
    )


def _visible_notifications(user_id: uuid.UUID, business_ids: list[uuid.UUID]) -> ColumnElement[bool]:
    return or_(
        Notification.user_id == user_id,
        and_(Notification.user_id.is_(None), _audience(Notification.business_id, business_ids)),
    )


async def _is_active_business(session: AsyncSession, business_id: uuid.UUID) -> bool:
    biz = await session.get(Business, business_id)
    return biz is not None and biz.status == "active"


async def list_promotions(
    session: AsyncSession, user: User, business_id: uuid.UUID | None = None
) -> PromotionsResponse:
    now = utcnow()
    if business_id is not None:
        active_window = and_(
            Promotion.is_active.is_(True),
            or_(Promotion.starts_at.is_(None), Promotion.starts_at <= now),
            or_(Promotion.ends_at.is_(None), Promotion.ends_at > now),
        )
        global_banners = and_(
            Promotion.business_id.is_(None),
            Promotion.kind == "banner",
        )
        if await _is_active_business(session, business_id):
            where_clause = and_(
                active_window,
                or_(
                    Promotion.business_id == business_id,
                    global_banners,
                ),
            )
        else:
            where_clause = and_(
                active_window,
                global_banners,
            )
    else:
        business_ids = await customer_business_ids(session, user.id)
        where_clause = _visible_promotions(business_ids, now)

    stmt = (
        select(Promotion)
        .where(where_clause)
        .order_by(Promotion.sort_order.asc(), Promotion.created_at.desc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    banners: list[PromotionItem] = []
    offers: list[PromotionItem] = []
    for promo in rows:
        item = PromotionItem.model_validate(promo)
        item.is_new = _is_new(promo.created_at, user.promotions_seen_at)
        (banners if promo.kind == "banner" else offers).append(item)
    return PromotionsResponse(
        banners=banners,
        offers=offers,
        has_new=any(item.is_new for item in offers),
    )


async def get_promotion(
    session: AsyncSession,
    user: User,
    promotion_id: uuid.UUID,
    business_id: uuid.UUID | None = None,
) -> PromotionItem:
    from app.core.errors import AppError

    now = utcnow()
    if business_id is not None:
        active_window = and_(
            Promotion.is_active.is_(True),
            or_(Promotion.starts_at.is_(None), Promotion.starts_at <= now),
            or_(Promotion.ends_at.is_(None), Promotion.ends_at > now),
        )
        global_banners = and_(
            Promotion.business_id.is_(None),
            Promotion.kind == "banner",
        )
        if await _is_active_business(session, business_id):
            allowed_scope = or_(
                Promotion.business_id == business_id,
                global_banners,
            )
        else:
            allowed_scope = global_banners

        conditions = [
            Promotion.id == promotion_id,
            active_window,
            allowed_scope,
        ]
    else:
        business_ids = await customer_business_ids(session, user.id)
        conditions = [
            Promotion.id == promotion_id,
            _visible_promotions(business_ids, now),
        ]

    promo = await session.scalar(select(Promotion).where(*conditions))
    if promo is None:
        raise AppError("PROMOTION_NOT_FOUND", "Promotion not found", 404)
    item = PromotionItem.model_validate(promo)
    item.is_new = _is_new(promo.created_at, user.promotions_seen_at)
    return item


def _notification_effective_time() -> ColumnElement[datetime]:
    return func.coalesce(Notification.scheduled_at, Notification.created_at)


async def _notification_visibility(
    session: AsyncSession, user: User, business_id: uuid.UUID | None
) -> ColumnElement[bool] | None:
    """The single visibility predicate shared by GET, unread counting and exact-ID mark-read.

    Returns None when nothing can be visible (business_id given but not an active business).
    Another customer's personal notifications and not-yet-due scheduled ones are never visible.
    """
    now = utcnow()
    eff_time = _notification_effective_time()
    time_filter = or_(Notification.scheduled_at.is_(None), Notification.scheduled_at <= now)

    if business_id is not None:
        if not await _is_active_business(session, business_id):
            return None
        return and_(
            Notification.business_id == business_id,
            time_filter,
            or_(
                Notification.user_id == user.id,
                and_(Notification.user_id.is_(None), eff_time >= user.created_at),
            ),
        )
    business_ids = await customer_business_ids(session, user.id)
    return and_(
        _visible_notifications(user.id, business_ids),
        time_filter,
        or_(Notification.user_id == user.id, eff_time >= user.created_at),
    )


def _notification_baseline_unread(user: User) -> ColumnElement[bool]:
    """Not covered by the legacy baseline (User.notifications_seen_at)."""
    if user.notifications_seen_at is None:
        return true()
    return _notification_effective_time() > user.notifications_seen_at


def _notification_unread(user: User) -> ColumnElement[bool]:
    """Unread = after the legacy baseline AND no per-user receipt for this notification."""
    no_receipt = ~exists().where(
        NotificationRead.user_id == user.id,
        NotificationRead.notification_id == Notification.id,
    )
    return and_(_notification_baseline_unread(user), no_receipt)


async def list_notifications(
    session: AsyncSession, user: User, business_id: uuid.UUID | None = None
) -> NotificationsResponse:
    now = utcnow()
    eff_time = _notification_effective_time()
    visible = await _notification_visibility(session, user, business_id)
    if visible is None:
        return NotificationsResponse(items=[], unread_count=0)

    rows = (
        await session.execute(
            select(Notification, RedemptionCode, Business, NotificationRead.notification_id)
            .outerjoin(RedemptionCode, RedemptionCode.id == Notification.redemption_id)
            .outerjoin(Business, Business.id == Notification.business_id)
            .outerjoin(
                NotificationRead,
                and_(
                    NotificationRead.user_id == user.id,
                    NotificationRead.notification_id == Notification.id,
                ),
            )
            .where(visible)
            .order_by(eff_time.desc(), Notification.id.desc())
            .limit(NOTIFICATIONS_PAGE_LIMIT)
        )
    ).all()
    items = []
    for notif, redemption, business, receipt_id in rows:
        item = NotificationItem.model_validate(notif)
        effective_at = notif.scheduled_at if notif.scheduled_at is not None else notif.created_at
        item.is_unread = _is_new(effective_at, user.notifications_seen_at) and receipt_id is None
        if notif.redemption_id is not None and redemption is not None:
            is_pending_and_valid = (
                redemption.status == "pending"
                and as_utc(redemption.expires_at) > now
            )
            if not is_pending_and_valid:
                biz_name = business.name if business else ""
                if redemption.status == "confirmed":
                    item.body = redemption_confirmed_text(redemption.amount, biz_name)
                else:
                    item.body = redemption_inactive_text(redemption.amount, biz_name)
        items.append(item)
    unread = await _unread_notifications(session, user, business_id=business_id)
    return NotificationsResponse(items=items, unread_count=unread)


async def _unread_notifications(
    session: AsyncSession,
    user: User,
    business_ids: list[uuid.UUID] | None = None,
    business_id: uuid.UUID | None = None,
) -> int:
    # `business_ids` is accepted for call compatibility; the shared predicate resolves it itself.
    visible = await _notification_visibility(session, user, business_id)
    if visible is None:
        return 0
    count = await session.scalar(
        select(func.count(Notification.id)).where(visible, _notification_unread(user))
    )
    return int(count or 0)


async def badges(
    session: AsyncSession, user: User, business_id: uuid.UUID | None = None
) -> BadgesResponse:
    if business_id is not None:
        if not await _is_active_business(session, business_id):
            return BadgesResponse(promotions_new=False, notifications_unread=0)
        now = utcnow()
        promo_conditions = [
            Promotion.business_id == business_id,
            Promotion.kind == "offer",
            Promotion.is_active.is_(True),
            or_(Promotion.starts_at.is_(None), Promotion.starts_at <= now),
            or_(Promotion.ends_at.is_(None), Promotion.ends_at > now),
        ]
    else:
        business_ids = await customer_business_ids(session, user.id)
        promo_conditions = [_visible_promotions(business_ids, utcnow()), Promotion.kind == "offer"]

    if user.promotions_seen_at is not None:
        promo_conditions.append(Promotion.created_at > user.promotions_seen_at)
    has_new_promo = await session.scalar(select(Promotion.id).where(*promo_conditions).limit(1))
    return BadgesResponse(
        promotions_new=has_new_promo is not None,
        notifications_unread=await _unread_notifications(
            session, user, business_id=business_id
        ),
    )


async def mark_promotions_seen(
    session: AsyncSession, user: User, business_id: uuid.UUID | None = None
) -> None:
    user.promotions_seen_at = utcnow()
    await session.commit()


async def mark_notifications_read(
    session: AsyncSession, user: User, business_id: uuid.UUID | None = None
) -> None:
    """LEGACY: moves the per-user baseline (all business modes alike; `business_id` is ignored).

    Kept unchanged for old app versions. Known limit: it still marks everything older than "now"
    as read for the whole user, including items the client never showed and other businesses.
    The exact-ID endpoint does not have this problem and never moves this baseline.
    """
    user.notifications_seen_at = utcnow()
    await session.commit()


async def mark_notifications_read_by_ids(
    session: AsyncSession,
    user: User,
    ids: list[uuid.UUID],
    business_id: uuid.UUID | None = None,
) -> NotificationMarkReadResponse:
    """Mark exactly the given notifications as read for this user (idempotent, race-safe).

    Duplicates are collapsed (first occurrence order). An id is "visible" iff the shared GET
    predicate shows it for the same `business_id` mode; everything else (unknown, foreign,
    another customer's personal, other business, not yet due, inactive business) lands in
    `ignored` without revealing why. Receipts are inserted by a single
    INSERT..SELECT..ON CONFLICT DO NOTHING RETURNING, so concurrent identical requests never
    duplicate and exactly one of them reports an id as `read`. The baseline is never touched.
    """
    requested = list(dict.fromkeys(ids))
    visibility = await _notification_visibility(session, user, business_id)
    if visibility is None:
        return NotificationMarkReadResponse(
            read=[], already_read=[], ignored=requested, unread_count=0
        )
    visible = set(
        (
            await session.execute(
                select(Notification.id).where(visibility, Notification.id.in_(requested))
            )
        ).scalars()
    )
    select_new = select(literal(user.id, type_=Uuid()), Notification.id).where(
        visibility,
        Notification.id.in_(requested),
        _notification_baseline_unread(user),
    )
    is_postgres = session.get_bind().dialect.name == "postgresql"
    dialect_insert = pg_insert if is_postgres else sqlite_insert
    stmt = (
        dialect_insert(NotificationRead)
        .from_select(["user_id", "notification_id"], select_new)
        .on_conflict_do_nothing(index_elements=["user_id", "notification_id"])
        .returning(NotificationRead.notification_id)
    )
    inserted = set((await session.execute(stmt)).scalars())
    await session.commit()
    unread = await _unread_notifications(session, user, business_id=business_id)
    return NotificationMarkReadResponse(
        read=[i for i in requested if i in inserted],
        already_read=[i for i in requested if i in visible and i not in inserted],
        ignored=[i for i in requested if i not in visible],
        unread_count=unread,
    )


def _amount_text(amount: Decimal) -> str:
    normalized = abs(amount).quantize(Decimal("0.01"))
    whole, _, fraction = f"{normalized:f}".partition(".")
    grouped = f"{int(whole):,}".replace(",", " ")
    return grouped if fraction in ("", "00") else f"{grouped},{fraction}"


def redemption_confirmed_text(amount: Decimal, business_name: str) -> str:
    if not amount or amount == 0:
        if business_name:
            return f"Списание в «{business_name}» подтверждено на кассе."
        return "Списание подтверждено на кассе."
    amount_str = _amount_text(amount)
    if business_name:
        return f"Списание {amount_str} бонусов в «{business_name}» подтверждено на кассе."
    return f"Списание {amount_str} бонусов подтверждено на кассе."


def redemption_inactive_text(amount: Decimal, business_name: str) -> str:
    if not amount or amount == 0:
        if business_name:
            return f"Код для списания в «{business_name}» больше не действует."
        return "Код больше не действует."
    amount_str = _amount_text(amount)
    if business_name:
        return f"Код для списания {amount_str} бонусов в «{business_name}» больше не действует."
    return f"Код для списания {amount_str} бонусов больше не действует."


def transaction_notification(
    user_id: uuid.UUID,
    business: Business,
    tx_type: str,
    amount: Decimal,
    balance_after: Decimal,
) -> Notification | None:
    """Notification for a fresh accrual / redemption mirrored from ONE."""
    if tx_type == "accrual":
        title = f"Начислено {_amount_text(amount)} бонусов"
    elif tx_type == "redemption":
        title = f"Списано {_amount_text(amount)} бонусов"
    else:
        return None
    return Notification(
        business_id=business.id,
        user_id=user_id,
        kind=tx_type,
        title=title,
        body=f"{business.name}. Баланс: {_amount_text(balance_after)} бонусов.",
    )


def is_fresh_transaction(occurred_at: datetime) -> bool:
    return as_utc(occurred_at) >= utcnow() - TRANSACTION_NOTIFY_WINDOW
