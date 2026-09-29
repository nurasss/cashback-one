from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_challenge_code, hash_challenge_code
from app.models.entities import LoginChallenge
from app.services.auth_confirmation import confirm_login_challenge


@pytest.mark.asyncio
async def test_confirm_login_challenge_valid(db_session: AsyncSession) -> None:
    """Valid code and sender phone successfully confirms challenge."""
    code = generate_challenge_code()
    challenge = LoginChallenge(
        device_id="dev-confirm-1",
        code_hash=hash_challenge_code(code),
        status="pending",
        expires_at=datetime.now(UTC) + timedelta(minutes=3),
    )
    db_session.add(challenge)
    await db_session.commit()

    # Confirm with local KZ phone format 8701...
    confirmed = await confirm_login_challenge(db_session, code, "87017778899")
    assert confirmed is not None
    assert confirmed.status == "confirmed"
    assert confirmed.phone == "+77017778899"  # Normalized to E.164
    assert confirmed.confirmed_at is not None

    # Check in DB
    refreshed = await db_session.get(LoginChallenge, challenge.id)
    assert refreshed is not None
    assert refreshed.status == "confirmed"
    assert refreshed.phone == "+77017778899"


@pytest.mark.asyncio
async def test_confirm_login_challenge_wrong_code(db_session: AsyncSession) -> None:
    """Non-existent code returns None."""
    result = await confirm_login_challenge(db_session, "WRONG123", "+77017778899")
    assert result is None


@pytest.mark.asyncio
async def test_confirm_login_challenge_expired_code(db_session: AsyncSession) -> None:
    """Expired challenge cannot be confirmed and returns None."""
    code = generate_challenge_code()
    challenge = LoginChallenge(
        device_id="dev-confirm-expired",
        code_hash=hash_challenge_code(code),
        status="pending",
        expires_at=datetime.now(UTC) - timedelta(seconds=10),
    )
    db_session.add(challenge)
    await db_session.commit()

    result = await confirm_login_challenge(db_session, code, "+77017778899")
    assert result is None

    # Verify status transitioned to expired
    refreshed = await db_session.get(LoginChallenge, challenge.id)
    assert refreshed is not None
    assert refreshed.status == "expired"


@pytest.mark.asyncio
async def test_confirm_login_challenge_repeated_same_phone_idempotent(
    db_session: AsyncSession,
) -> None:
    """Repeated confirmation with the same phone is safe and idempotent."""
    code = generate_challenge_code()
    challenge = LoginChallenge(
        device_id="dev-confirm-repeat",
        code_hash=hash_challenge_code(code),
        status="pending",
        expires_at=datetime.now(UTC) + timedelta(minutes=3),
    )
    db_session.add(challenge)
    await db_session.commit()

    res1 = await confirm_login_challenge(db_session, code, "+77011112233")
    assert res1 is not None
    assert res1.phone == "+77011112233"

    res2 = await confirm_login_challenge(db_session, code, "+77011112233")
    assert res2 is not None
    assert res2.phone == "+77011112233"


@pytest.mark.asyncio
async def test_confirm_login_challenge_second_phone_cannot_steal(
    db_session: AsyncSession,
) -> None:
    """If a code is already confirmed, a second phone cannot overwrite the identity."""
    code = generate_challenge_code()
    challenge = LoginChallenge(
        device_id="dev-confirm-steal",
        code_hash=hash_challenge_code(code),
        status="pending",
        expires_at=datetime.now(UTC) + timedelta(minutes=3),
    )
    db_session.add(challenge)
    await db_session.commit()

    # First user confirms
    res1 = await confirm_login_challenge(db_session, code, "+77011112233")
    assert res1 is not None
    assert res1.phone == "+77011112233"

    # Second user tries to confirm with same code
    res2 = await confirm_login_challenge(db_session, code, "+77099990000")
    assert res2 is not None
    # Must STILL be first user's phone!
    assert res2.phone == "+77011112233"

    refreshed = await db_session.get(LoginChallenge, challenge.id)
    assert refreshed is not None
    assert refreshed.phone == "+77011112233"
