from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.phone import normalize_phone
from app.core.security import hash_challenge_code
from app.core.time import as_utc, utcnow
from app.models.entities import LoginChallenge


async def confirm_login_challenge(
    session: AsyncSession,
    code: str,
    sender_phone: str,
) -> LoginChallenge | None:
    """Internal provider-independent domain service to confirm a WhatsApp login challenge.

    This service will be invoked by future WhatsApp/Wappi webhook adapters.
    It verifies the HMAC digest, validates TTL, binds the normalized sender phone,
    and transitions challenge status from 'pending' to 'confirmed' atomically.
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
        return None

    # Check expiration
    if as_utc(challenge.expires_at) <= utcnow():
        if challenge.status == "pending":
            challenge.status = "expired"
            await session.commit()
        return None

    # If already confirmed:
    # Idempotent if confirmed by the same phone.
    # If a second phone tries to claim the same code, first confirmation remains source of truth.
    if challenge.status == "confirmed":
        return challenge

    # If already consumed:
    if challenge.status == "consumed":
        return challenge

    # Transition from pending to confirmed
    if challenge.status == "pending":
        challenge.phone = normalized_phone
        challenge.status = "confirmed"
        challenge.confirmed_at = utcnow()
        await session.commit()
        return challenge

    return challenge
