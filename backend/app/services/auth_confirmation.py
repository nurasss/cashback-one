import uuid
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.phone import normalize_phone
from app.core.security import hash_challenge_code
from app.core.time import as_utc, utcnow
from app.models.entities import LoginChallenge


class ConfirmationStatus(str, Enum):
    CONFIRMED = "confirmed"
    ALREADY_CONFIRMED_SAME_PHONE = "already_confirmed_same_phone"
    ALREADY_CONFIRMED_OTHER_PHONE = "already_confirmed_other_phone"
    EXPIRED = "expired"
    NOT_FOUND = "not_found"
    CONSUMED = "consumed"


@dataclass(frozen=True)
class ConfirmationResult:
    status: ConfirmationStatus
    challenge_id: uuid.UUID | None = None
    is_success: bool = False
    error_message: str | None = None


async def confirm_login_challenge(
    session: AsyncSession,
    code: str,
    sender_phone: str,
) -> ConfirmationResult:
    """Internal provider-independent domain service to confirm a WhatsApp login challenge.

    This service will be invoked by future WhatsApp/Wappi webhook adapters.
    It verifies the HMAC digest, validates TTL, binds the normalized sender phone,
    and transitions challenge status from 'pending' to 'confirmed' atomically.

    Guarantees strict phone isolation: if another phone attempts to confirm an already
    confirmed challenge, it returns ALREADY_CONFIRMED_OTHER_PHONE and does not expose
    the original phone number.
    """
    normalized_code = code.strip().upper()
    try:
        normalized_phone = normalize_phone(sender_phone)
    except ValueError as err:
        raise AppError(
            code="INVALID_PHONE_FORMAT",
            message=f"Invalid sender phone number: {err}",
            status_code=422,
        ) from err

    code_digest = hash_challenge_code(normalized_code)

    # Acquire row lock on the challenge to guarantee atomic state transition under concurrent events
    stmt = (
        select(LoginChallenge)
        .where(LoginChallenge.code_hash == code_digest)
        .with_for_update()
    )
    challenge = (await session.execute(stmt)).scalar_one_or_none()

    if not challenge:
        return ConfirmationResult(
            status=ConfirmationStatus.NOT_FOUND,
            challenge_id=None,
            is_success=False,
            error_message="Challenge not found",
        )

    # Check expiration
    if as_utc(challenge.expires_at) <= utcnow():
        if challenge.status == "pending":
            challenge.status = "expired"
            await session.commit()
        return ConfirmationResult(
            status=ConfirmationStatus.EXPIRED,
            challenge_id=challenge.id,
            is_success=False,
            error_message="Challenge has expired",
        )

    # If already consumed:
    if challenge.status == "consumed":
        return ConfirmationResult(
            status=ConfirmationStatus.CONSUMED,
            challenge_id=challenge.id,
            is_success=False,
            error_message="Challenge has already been exchanged for tokens",
        )

    # If already confirmed:
    if challenge.status == "confirmed":
        if challenge.phone == normalized_phone:
            return ConfirmationResult(
                status=ConfirmationStatus.ALREADY_CONFIRMED_SAME_PHONE,
                challenge_id=challenge.id,
                is_success=True,
            )
        return ConfirmationResult(
            status=ConfirmationStatus.ALREADY_CONFIRMED_OTHER_PHONE,
            challenge_id=challenge.id,
            is_success=False,
            error_message="Challenge was confirmed by another phone number",
        )

    # Transition from pending to confirmed
    if challenge.status == "pending":
        challenge.phone = normalized_phone
        challenge.status = "confirmed"
        challenge.confirmed_at = utcnow()
        await session.commit()
        return ConfirmationResult(
            status=ConfirmationStatus.CONFIRMED,
            challenge_id=challenge.id,
            is_success=True,
        )

    return ConfirmationResult(
        status=ConfirmationStatus.NOT_FOUND,
        challenge_id=challenge.id,
        is_success=False,
    )

