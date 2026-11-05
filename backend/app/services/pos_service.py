"""Service handling POS direct cloud redemptions with 4-digit push codes."""
import hmac
import uuid
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import generate_sms_otp
from app.core.time import as_utc, utcnow
from app.models.entities import Business, Card, Notification, PosKey, RedemptionCode, User, UserCard
from app.schemas.pos import PosRedemptionRequest, PosRedemptionResponse, RedemptionVerifyResponse
from app.services.content_service import (
    _amount_text,
    redemption_confirmed_text,
    redemption_inactive_text,
)
from app.services.push_sender import PushSender
from app.services.push_service import has_active_device, send_to_user
from app.services.rate_limiter import RateLimiter
from app.services.redemption_service import _hash_code


async def request_pos_redemption(
    session: AsyncSession,
    pos_key: PosKey,
    body: PosRedemptionRequest,
    limiter: RateLimiter,
    sender: PushSender,
) -> PosRedemptionResponse:
    """Request a write-off confirmation code delivered to the customer via push notification."""
    if sender.disabled:
        raise AppError(
            code="PUSH_NOT_CONFIGURED",
            message="Push delivery is not configured on this server.",
            status_code=503,
        )

    card = await session.scalar(
        select(Card).where(Card.barcode == body.barcode, Card.business_id == pos_key.business_id)
    )
    if card is None:
        raise AppError("CARD_NOT_FOUND", "Card not found in this business", 404)
    if card.is_blocked:
        raise AppError("CARD_BLOCKED", "Card is blocked", 409)

    owner = await session.scalar(
        select(User)
        .join(UserCard, UserCard.user_id == User.id)
        .where(UserCard.card_id == card.id, User.deleted_at.is_(None))
    )
    if owner is None:
        raise AppError(
            "CUSTOMER_NO_APP",
            "Customer does not have Cashback One app",
            409,
        )

    active = await has_active_device(session, owner.id, business_id=pos_key.business_id)
    if not active:
        raise AppError(
            "CUSTOMER_NO_APP",
            "Customer has no active devices with notifications enabled",
            409,
        )

    if await limiter.is_rate_limited(
        f"redeem:card:{card.id}",
        settings.redemption_card_request_limit,
        settings.redemption_card_rate_window_seconds,
    ):
        raise AppError("RATE_LIMIT_EXCEEDED", "Too many code requests for this card", 429)

    code = generate_sms_otp(4)
    record_id = uuid.uuid4()
    now = utcnow()

    business_name = (
        await session.scalar(select(Business.name).where(Business.id == pos_key.business_id))
    ) or ""
    amount_text = _amount_text(body.amount)
    title = "Код для списания баллов"
    text = (
        f"Код {code} для списания {amount_text} баллов в «{business_name}». "
        "Назовите его кассиру, только если сейчас оплачиваете покупку."
    )
    data = {"type": "redemption_code", "redemption_id": str(record_id)}

    try:
        delivered = await send_to_user(
            session=session,
            sender=sender,
            user_id=owner.id,
            title=title,
            body=text,
            data=data,
            business_id=pos_key.business_id,
        )
    except AppError:
        raise
    except Exception:  # noqa: BLE001 - any send error results in 503
        raise AppError("PUSH_DELIVERY_FAILED", "Failed to deliver push notification", 503)

    if delivered == 0:
        raise AppError("PUSH_DELIVERY_FAILED", "Failed to deliver push notification", 503)

    prev_pendings = (
        await session.execute(
            select(RedemptionCode)
            .where(RedemptionCode.card_id == card.id, RedemptionCode.status == "pending")
        )
    ).scalars().all()
    for prev in prev_pendings:
        prev.status = "superseded"
        await session.execute(
            update(Notification)
            .where(Notification.redemption_id == prev.id)
            .values(body=redemption_inactive_text(prev.amount, business_name))
        )

    record = RedemptionCode(
        id=record_id,
        business_id=pos_key.business_id,
        card_id=card.id,
        amount=body.amount,
        code_hash=_hash_code(record_id, code),
        expires_at=now + timedelta(seconds=settings.redemption_code_ttl_seconds),
        created_at=now,
    )
    session.add(record)
    await session.flush()

    notification = Notification(
        id=uuid.uuid4(),
        business_id=pos_key.business_id,
        user_id=owner.id,
        redemption_id=record_id,
        kind="info",
        title=title,
        body=text,
        created_at=now,
    )
    session.add(notification)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    return PosRedemptionResponse(
        redemption_id=record.id,
        expires_at=record.expires_at,
    )


async def verify_pos_redemption(
    session: AsyncSession,
    pos_key: PosKey,
    redemption_id: uuid.UUID,
    code: str,
) -> RedemptionVerifyResponse:
    """Verify customer redemption code entered by cashier."""
    record = await session.scalar(
        select(RedemptionCode)
        .where(
            RedemptionCode.id == redemption_id,
            RedemptionCode.business_id == pos_key.business_id,
        )
        .with_for_update()
    )
    if record is None:
        raise AppError("REDEMPTION_NOT_FOUND", "Redemption request not found", 404)
    if record.status == "confirmed":
        raise AppError("REDEMPTION_ALREADY_CONFIRMED", "Code was already used", 409)
    if record.status != "pending":
        raise AppError("REDEMPTION_NOT_ACTIVE", "Request a new code", 409)

    business_name = (
        await session.scalar(select(Business.name).where(Business.id == pos_key.business_id))
    ) or ""

    if as_utc(record.expires_at) <= utcnow():
        record.status = "expired"
        await session.execute(
            update(Notification)
            .where(Notification.redemption_id == record.id)
            .values(body=redemption_inactive_text(record.amount, business_name))
        )
        await session.commit()
        raise AppError("REDEMPTION_EXPIRED", "Code has expired", 409)

    if not hmac.compare_digest(_hash_code(record.id, code), record.code_hash):
        record.attempts += 1
        if record.attempts >= settings.redemption_code_max_attempts:
            record.status = "exhausted"
            await session.execute(
                update(Notification)
                .where(Notification.redemption_id == record.id)
                .values(body=redemption_inactive_text(record.amount, business_name))
            )
            await session.commit()
            raise AppError("REDEMPTION_MAX_ATTEMPTS_EXCEEDED", "Too many wrong codes", 409)
        await session.commit()
        raise AppError("INVALID_CODE", "Invalid code", 400)

    record.status = "confirmed"
    record.verified_at = utcnow()
    await session.execute(
        update(Notification)
        .where(Notification.redemption_id == record.id)
        .values(body=redemption_confirmed_text(record.amount, business_name))
    )
    card = await session.get_one(Card, record.card_id)
    await session.commit()

    return RedemptionVerifyResponse(
        status="confirmed",
        barcode=card.barcode,
        amount=Decimal(record.amount),
    )
