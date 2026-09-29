from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_challenge_code, hash_challenge_code
from app.models.entities import LoginChallenge
from app.services.auth_confirmation import (
    ConfirmationResult,
    ConfirmationStatus,
    confirm_login_challenge,
)


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
    result = await confirm_login_challenge(db_session, code, "87017778899")
    assert isinstance(result, ConfirmationResult)
    assert result.is_success is True
    assert result.status == ConfirmationStatus.CONFIRMED
    assert result.challenge_id == challenge.id

    # Check in DB
    refreshed = await db_session.get(LoginChallenge, challenge.id)
    assert refreshed is not None
    assert refreshed.status == "confirmed"
    assert refreshed.phone == "+77017778899"
    assert refreshed.confirmed_at is not None


@pytest.mark.asyncio
async def test_confirm_login_challenge_wrong_code(db_session: AsyncSession) -> None:
    """Non-existent code returns NOT_FOUND status."""
    result = await confirm_login_challenge(db_session, "WRONG123", "+77017778899")
    assert isinstance(result, ConfirmationResult)
    assert result.is_success is False
    assert result.status == ConfirmationStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_confirm_login_challenge_expired_code(db_session: AsyncSession) -> None:
    """Expired challenge cannot be confirmed and returns EXPIRED status."""
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
    assert isinstance(result, ConfirmationResult)
    assert result.is_success is False
    assert result.status == ConfirmationStatus.EXPIRED

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
    assert res1.is_success is True
    assert res1.status == ConfirmationStatus.CONFIRMED

    res2 = await confirm_login_challenge(db_session, code, "+77011112233")
    assert res2.is_success is True
    assert res2.status == ConfirmationStatus.ALREADY_CONFIRMED_SAME_PHONE


@pytest.mark.asyncio
async def test_confirm_login_challenge_second_phone_cannot_steal(
    db_session: AsyncSession,
) -> None:
    """If a code is already confirmed, a second phone cannot overwrite the identity or receive success."""
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
    assert res1.is_success is True
    assert res1.status == ConfirmationStatus.CONFIRMED

    # Second user tries to confirm with same code
    res2 = await confirm_login_challenge(db_session, code, "+77099990000")
    assert res2.is_success is False
    assert res2.status == ConfirmationStatus.ALREADY_CONFIRMED_OTHER_PHONE
    assert res2.error_message is not None

    # DB still preserves the first user's phone exclusively
    refreshed = await db_session.get(LoginChallenge, challenge.id)
    assert refreshed is not None
    assert refreshed.phone == "+77011112233"


@pytest.mark.asyncio
async def test_confirm_login_challenge_consumed_returns_consumed(
    db_session: AsyncSession,
) -> None:
    """A consumed challenge returns CONSUMED status."""
    code = generate_challenge_code()
    challenge = LoginChallenge(
        device_id="dev-confirm-consumed",
        code_hash=hash_challenge_code(code),
        status="consumed",
        expires_at=datetime.now(UTC) + timedelta(minutes=3),
        phone="+77011112233",
    )
    db_session.add(challenge)
    await db_session.commit()

    result = await confirm_login_challenge(db_session, code, "+77011112233")
    assert result.is_success is False
    assert result.status == ConfirmationStatus.CONSUMED


@pytest.mark.parametrize("invalid_phone", ["", "   ", "\t\n"])
@pytest.mark.asyncio
async def test_confirm_login_challenge_empty_phone_rejected_remains_pending(
    db_session: AsyncSession, invalid_phone: str
) -> None:
    """Regression test (TASK-004 Carry-over fix): Empty/whitespace phone raises 422, challenge stays pending."""
    from app.core.errors import AppError

    code = generate_challenge_code()
    challenge = LoginChallenge(
        device_id="dev-confirm-empty-phone",
        code_hash=hash_challenge_code(code),
        status="pending",
        expires_at=datetime.now(UTC) + timedelta(minutes=3),
    )
    db_session.add(challenge)
    await db_session.commit()

    with pytest.raises(AppError) as exc_info:
        await confirm_login_challenge(db_session, code, invalid_phone)

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "INVALID_PHONE_FORMAT"

    # Crucial invariant: Challenge must remain strictly pending and phone must be NULL
    refreshed = await db_session.get(LoginChallenge, challenge.id)
    assert refreshed is not None
    assert refreshed.status == "pending"
    assert refreshed.phone is None
    assert refreshed.confirmed_at is None


@pytest.mark.asyncio
async def test_confirm_login_challenge_without_immediate_commit(
    db_session: AsyncSession,
) -> None:
    """When commit=False, caller controls transaction lifecycle."""
    code = generate_challenge_code()
    challenge = LoginChallenge(
        device_id="dev-confirm-no-commit",
        code_hash=hash_challenge_code(code),
        status="pending",
        expires_at=datetime.now(UTC) + timedelta(minutes=3),
    )
    db_session.add(challenge)
    await db_session.commit()

    c_id = challenge.id
    res = await confirm_login_challenge(db_session, code, "+77015554433", commit=False)
    assert res.is_success is True
    assert res.status == ConfirmationStatus.CONFIRMED

    # Roll back instead of commit
    await db_session.rollback()

    # Verify rollback: status must still be pending
    refreshed = await db_session.get(LoginChallenge, c_id)
    assert refreshed is not None
    assert refreshed.status == "pending"
    assert refreshed.phone is None


