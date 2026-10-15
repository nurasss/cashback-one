"""POS bonus write-off confirmation: one-time code delivered to the customer's WhatsApp.

The write-off itself stays in POSCENTER ONE. The POS asks the cloud for a code, the customer
reads it from WhatsApp, and the POS verifies it here before posting the write-off in ONE.
"""
import hashlib
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
from app.models.entities import Agent, Business, Card, RedemptionCode, User, UserCard
from app.schemas.pos import RedemptionRequest, RedemptionRequestResponse, RedemptionVerifyResponse
from app.services.content_service import _amount_text
from app.services.qr_tokens import verify_card_token
from app.services.rate_limiter import RateLimiter
from app.services.whatsapp_sender import WhatsAppSender


def _hash_code(redemption_id: uuid.UUID, code: str) -> str:
    payload = f"redeem:{redemption_id}:{code.strip()}".encode()
    return hmac.new(settings.sms_otp_hash_key.encode(), payload, hashlib.sha256).hexdigest()


def mask_phone(phone: str) -> str:
    return phone[:4] + "*" * max(len(phone) - 6, 0) + phone[-2:] if len(phone) > 6 else "***"


async def resolve_card(
    session: AsyncSession, agent: Agent, barcode: str | None, qr_token: str | None
) -> Card:
    """Find a card of the agent's business by barcode or dynamic QR token."""
    if qr_token:
        card_id = verify_card_token(qr_token)
        if card_id is None:
            raise AppError("QR_TOKEN_INVALID", "QR code is invalid or expired", 422)
        condition = Card.id == card_id
    elif barcode:
        condition = Card.barcode == barcode
    else:
        raise AppError("CARD_REFERENCE_REQUIRED", "Provide barcode or qr_token", 422)
    card = await session.scalar(
        select(Card).where(condition, Card.business_id == agent.business_id)
    )
    if card is None:
        raise AppError("CARD_NOT_FOUND", "Card not found", 404)
    return card


async def _recipient_phone(session: AsyncSession, card: Card) -> str | None:
    owner_phone = await session.scalar(
        select(User.phone)
        .join(UserCard, UserCard.user_id == User.id)
        .where(UserCard.card_id == card.id, User.deleted_at.is_(None))
    )
    return owner_phone or card.phone


async def request_redemption(
    session: AsyncSession,
    agent: Agent,
    body: RedemptionRequest,
    limiter: RateLimiter,
    sender: WhatsAppSender,
) -> RedemptionRequestResponse:
    if sender.disabled:
        raise AppError(
            "WHATSAPP_NOT_CONFIGURED", "WhatsApp delivery is not configured on this server.", 503
        )
    card = await resolve_card(session, agent, body.barcode, body.qr_token)
    if card.is_blocked:
        raise AppError("CARD_BLOCKED", "Card is blocked", 409)
    phone = await _recipient_phone(session, card)
    if not phone:
        raise AppError("REDEMPTION_PHONE_MISSING", "Card has no phone to send the code to", 409)
    if await limiter.is_rate_limited(
        f"redeem:card:{card.id}",
        settings.redemption_card_request_limit,
        settings.redemption_card_rate_window_seconds,
    ):
        raise AppError("RATE_LIMIT_EXCEEDED", "Too many code requests for this card", 429)

    await session.execute(
        update(RedemptionCode)
        .where(RedemptionCode.card_id == card.id, RedemptionCode.status == "pending")
        .values(status="superseded")
    )
    code = generate_sms_otp()
    now = utcnow()
    record = RedemptionCode(
        id=uuid.uuid4(),
        business_id=agent.business_id,
        card_id=card.id,
        amount=body.amount,
        code_hash="",
        expires_at=now + timedelta(seconds=settings.redemption_code_ttl_seconds),
        created_at=now,
    )
    record.code_hash = _hash_code(record.id, code)
    session.add(record)

    business_name = await session.scalar(select(Business.name).where(Business.id == agent.business_id))
    try:
        await sender.send_text(
            phone,
            f"Код для списания {_amount_text(body.amount)} баллов в «{business_name}»: {code}\n"
            "Назовите его кассиру, только если вы сейчас оплачиваете покупку.",
        )
    except AppError:
        await session.rollback()
        raise
    await session.commit()
    return RedemptionRequestResponse(
        redemption_id=record.id,
        expires_at=record.expires_at,
        recipient=mask_phone(phone),
    )


async def verify_redemption(
    session: AsyncSession, agent: Agent, redemption_id: uuid.UUID, code: str
) -> RedemptionVerifyResponse:
    record = await session.scalar(
        select(RedemptionCode)
        .where(
            RedemptionCode.id == redemption_id,
            RedemptionCode.business_id == agent.business_id,
        )
        .with_for_update()
    )
    if record is None:
        raise AppError("REDEMPTION_NOT_FOUND", "Redemption request not found", 404)
    if record.status == "confirmed":
        raise AppError("REDEMPTION_ALREADY_CONFIRMED", "Code was already used", 409)
    if record.status != "pending":
        raise AppError("REDEMPTION_NOT_ACTIVE", "Request a new code", 409)
    if as_utc(record.expires_at) <= utcnow():
        record.status = "expired"
        await session.commit()
        raise AppError("REDEMPTION_EXPIRED", "Code has expired", 409)
    if not hmac.compare_digest(_hash_code(record.id, code), record.code_hash):
        record.attempts += 1
        if record.attempts >= settings.redemption_code_max_attempts:
            record.status = "exhausted"
            await session.commit()
            raise AppError("REDEMPTION_MAX_ATTEMPTS_EXCEEDED", "Too many wrong codes", 409)
        await session.commit()
        raise AppError("INVALID_CODE", "Invalid code", 400)
    record.status = "confirmed"
    record.verified_at = utcnow()
    card = await session.get_one(Card, record.card_id)
    await session.commit()
    return RedemptionVerifyResponse(
        status="confirmed",
        barcode=card.barcode,
        amount=Decimal(record.amount),
    )
