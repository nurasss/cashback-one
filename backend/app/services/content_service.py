"""Customer-facing content: promotions, notifications and the "new" badges."""
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement

from app.core.time import as_utc, utcnow
from app.models.entities import Business, Card, Notification, Promotion, User, UserCard
from app.schemas.customer_app import (
    BadgesResponse,
    NotificationItem,
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


async def list_promotions(session: AsyncSession, user: User) -> PromotionsResponse:
    business_ids = await customer_business_ids(session, user.id)
    stmt = (
        select(Promotion)
        .where(_visible_promotions(business_ids, utcnow()))
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


async def get_promotion(session: AsyncSession, user: User, promotion_id: uuid.UUID) -> PromotionItem:
    from app.core.errors import AppError

    business_ids = await customer_business_ids(session, user.id)
    promo = await session.scalar(
        select(Promotion).where(
            Promotion.id == promotion_id, _visible_promotions(business_ids, utcnow())
        )
    )
    if promo is None:
        raise AppError("PROMOTION_NOT_FOUND", "Promotion not found", 404)
    item = PromotionItem.model_validate(promo)
    item.is_new = _is_new(promo.created_at, user.promotions_seen_at)
    return item


async def list_notifications(session: AsyncSession, user: User) -> NotificationsResponse:
    business_ids = await customer_business_ids(session, user.id)
    visible = _visible_notifications(user.id, business_ids)
    # Customers never see broadcasts sent before they registered.
    since = Notification.created_at >= user.created_at
    rows = (
        await session.execute(
            select(Notification)
            .where(visible, or_(Notification.user_id == user.id, since))
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .limit(NOTIFICATIONS_PAGE_LIMIT)
        )
    ).scalars().all()
    items = []
    for row in rows:
        item = NotificationItem.model_validate(row)
        item.is_unread = _is_new(row.created_at, user.notifications_seen_at)
        items.append(item)
    unread = await _unread_notifications(session, user, business_ids)
    return NotificationsResponse(items=items, unread_count=unread)


async def _unread_notifications(
    session: AsyncSession, user: User, business_ids: list[uuid.UUID]
) -> int:
    conditions = [
        _visible_notifications(user.id, business_ids),
        or_(Notification.user_id == user.id, Notification.created_at >= user.created_at),
    ]
    if user.notifications_seen_at is not None:
        conditions.append(Notification.created_at > user.notifications_seen_at)
    count = await session.scalar(select(func.count(Notification.id)).where(*conditions))
    return int(count or 0)


async def badges(session: AsyncSession, user: User) -> BadgesResponse:
    business_ids = await customer_business_ids(session, user.id)
    promo_conditions = [_visible_promotions(business_ids, utcnow()), Promotion.kind == "offer"]
    if user.promotions_seen_at is not None:
        promo_conditions.append(Promotion.created_at > user.promotions_seen_at)
    has_new_promo = await session.scalar(select(Promotion.id).where(*promo_conditions).limit(1))
    return BadgesResponse(
        promotions_new=has_new_promo is not None,
        notifications_unread=await _unread_notifications(session, user, business_ids),
    )


async def mark_promotions_seen(session: AsyncSession, user: User) -> None:
    user.promotions_seen_at = utcnow()
    await session.commit()


async def mark_notifications_read(session: AsyncSession, user: User) -> None:
    user.notifications_seen_at = utcnow()
    await session.commit()


def _amount_text(amount: Decimal) -> str:
    normalized = abs(amount).quantize(Decimal("0.01"))
    whole, _, fraction = f"{normalized:f}".partition(".")
    grouped = f"{int(whole):,}".replace(",", " ")
    return grouped if fraction in ("", "00") else f"{grouped},{fraction}"


def transaction_notification(
    user_id: uuid.UUID,
    business: Business,
    tx_type: str,
    amount: Decimal,
    balance_after: Decimal,
) -> Notification | None:
    """Notification for a fresh accrual / redemption mirrored from ONE."""
    if tx_type == "accrual":
        title = f"Начислено {_amount_text(amount)} баллов"
    elif tx_type == "redemption":
        title = f"Списано {_amount_text(amount)} баллов"
    else:
        return None
    return Notification(
        business_id=business.id,
        user_id=user_id,
        kind=tx_type,
        title=title,
        body=f"{business.name}. Баланс: {_amount_text(balance_after)} баллов.",
    )


def is_fresh_transaction(occurred_at: datetime) -> bool:
    return as_utc(occurred_at) >= utcnow() - TRANSACTION_NOTIFY_WINDOW
