import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_refresh_token,
)
from app.models.entities import AuthSession, User
from app.services.auth_confirmation import confirm_login_challenge
from app.services.user_service import get_or_create_user_by_phone


@pytest.mark.asyncio
async def test_user_identity_creation_and_reuse(db_session: AsyncSession) -> None:
    """First auth creates User; subsequent auths with same/equivalent phone reuse User."""
    user1 = await get_or_create_user_by_phone(db_session, "87011234567")
    await db_session.commit()
    assert user1.phone == "+77011234567"

    # Same phone in different format (+7...)
    user2 = await get_or_create_user_by_phone(db_session, "+77011234567")
    await db_session.commit()
    assert user1.id == user2.id

    # Same phone in 7701... format
    user3 = await get_or_create_user_by_phone(db_session, "77011234567")
    await db_session.commit()
    assert user1.id == user3.id

    # Total users with this phone in DB must be exactly 1
    users = (
        await db_session.scalars(
            select(User).where(User.phone == "+77011234567")
        )
    ).all()
    assert len(users) == 1


@pytest.mark.asyncio
async def test_user_language_preserved_on_repeated_login(db_session: AsyncSession) -> None:
    """Subsequent logins must never reset user profile preferences (such as language kz)."""
    user = await get_or_create_user_by_phone(db_session, "+77015556677", language="kz")
    await db_session.commit()
    assert user.language == "kz"

    # Second login with default language="ru" must NOT overwrite user's "kz"
    user_repeat = await get_or_create_user_by_phone(db_session, "+77015556677", language="ru")
    await db_session.commit()
    assert user_repeat.id == user.id
    assert user_repeat.language == "kz"

    refreshed = await db_session.get(User, user.id)
    assert refreshed is not None
    assert refreshed.language == "kz"


def test_access_jwt_valid_claims_and_verification() -> None:
    """Access JWT contains required claims and decodes successfully."""
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    token = create_access_token(user_id=user_id, session_id=session_id)

    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["sid"] == str(session_id)
    assert payload["typ"] == "access"
    assert "iat" in payload
    assert "exp" in payload
    assert payload["exp"] > payload["iat"]


def test_access_jwt_tampered_rejected() -> None:
    """Tampered access JWT is rejected."""
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    token = create_access_token(user_id=user_id, session_id=session_id)

    tampered = token[:-5] + "XXXXX"
    with pytest.raises(AppError) as exc_info:
        decode_access_token(tampered)
    assert exc_info.value.code == "INVALID_TOKEN"


def test_access_jwt_expired_rejected() -> None:
    """Expired access JWT is rejected."""
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    expired_token = create_access_token(
        user_id=user_id,
        session_id=session_id,
        expires_delta_seconds=-10,
    )

    with pytest.raises(AppError) as exc_info:
        decode_access_token(expired_token)
    assert exc_info.value.code == "TOKEN_EXPIRED"


@pytest.mark.asyncio
async def test_refresh_token_stored_only_as_hash(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Plain refresh token is returned to client but never stored in DB."""
    create_res = await client.post("/auth/challenge", json={"device_id": "dev-hash-test"})
    c_id = create_res.json()["challenge_id"]
    code = create_res.json()["code"]

    await confirm_login_challenge(db_session, code, "+77019991122")

    poll = await client.get(f"/auth/challenge/{c_id}", headers={"X-Device-Id": "dev-hash-test"})
    raw_refresh = poll.json()["refresh_token"]

    # Verify DB has hash, not plaintext
    session_record = await db_session.scalar(select(AuthSession))
    assert session_record is not None
    assert session_record.refresh_token_hash != raw_refresh
    assert session_record.refresh_token_hash == hash_refresh_token(raw_refresh)


@pytest.mark.asyncio
async def test_refresh_token_rotation_flow(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """POST /auth/refresh rotates token: old token invalid, new token works."""
    create_res = await client.post("/auth/challenge", json={"device_id": "dev-rot-1"})
    c_id = create_res.json()["challenge_id"]
    code = create_res.json()["code"]

    await confirm_login_challenge(db_session, code, "+77015554433")

    poll = await client.get(f"/auth/challenge/{c_id}", headers={"X-Device-Id": "dev-rot-1"})
    r1 = poll.json()["refresh_token"]

    # First rotation
    rotate_res = await client.post("/auth/refresh", json={"refresh_token": r1})
    assert rotate_res.status_code == 200
    data_rot = rotate_res.json()
    r2 = data_rot["refresh_token"]
    assert r2 != r1

    # Replaying old refresh token r1 must fail
    replay_res = await client.post("/auth/refresh", json={"refresh_token": r1})
    assert replay_res.status_code == 401
    assert replay_res.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"

    # New refresh token r2 must work
    rotate_res_2 = await client.post("/auth/refresh", json={"refresh_token": r2})
    assert rotate_res_2.status_code == 200
    r3 = rotate_res_2.json()["refresh_token"]
    assert r3 != r2


@pytest.mark.asyncio
async def test_refresh_on_day_300_renews_session_through_day_400(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_res = await client.post("/auth/challenge", json={"device_id": "dev-sliding-ttl"})
    challenge_id = create_res.json()["challenge_id"]
    await confirm_login_challenge(db_session, create_res.json()["code"], "+77015550001")
    poll = await client.get(
        f"/auth/challenge/{challenge_id}", headers={"X-Device-Id": "dev-sliding-ttl"}
    )
    first_refresh = poll.json()["refresh_token"]
    session_record = await db_session.scalar(select(AuthSession))
    assert session_record is not None

    issued_at = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
    session_record.created_at = issued_at
    session_record.expires_at = issued_at + timedelta(days=365)
    await db_session.commit()

    clock = {"now": issued_at + timedelta(days=300)}
    monkeypatch.setattr("app.api.auth.utcnow", lambda: clock["now"])
    day_300 = await client.post("/auth/refresh", json={"refresh_token": first_refresh})
    assert day_300.status_code == 200
    second_refresh = day_300.json()["refresh_token"]
    assert session_record.expires_at == clock["now"] + timedelta(days=365)

    clock["now"] = issued_at + timedelta(days=400)
    day_400 = await client.post("/auth/refresh", json={"refresh_token": second_refresh})
    assert day_400.status_code == 200
    assert session_record.expires_at == clock["now"] + timedelta(days=365)


async def _issue_session(client: AsyncClient, db_session: AsyncSession, device: str, phone: str):
    create_res = await client.post("/auth/challenge", json={"device_id": device})
    challenge_id = create_res.json()["challenge_id"]
    await confirm_login_challenge(db_session, create_res.json()["code"], phone)
    poll = await client.get(f"/auth/challenge/{challenge_id}", headers={"X-Device-Id": device})
    session_record = await db_session.scalar(select(AuthSession))
    assert session_record is not None
    return poll.json()["refresh_token"], session_record


@pytest.mark.asyncio
async def test_challenge_session_is_issued_for_365_days_and_admin_ttl_is_unchanged(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    from app.core.config import settings

    _, record = await _issue_session(client, db_session, "dev-ttl-365", "+77015550002")
    lifetime = record.expires_at.replace(tzinfo=UTC) - record.created_at.replace(tzinfo=UTC)
    assert timedelta(days=365) - timedelta(minutes=1) < lifetime <= timedelta(days=365)
    assert settings.refresh_token_ttl_seconds == 365 * 86400
    assert settings.admin_refresh_token_ttl_seconds == 28800


@pytest.mark.asyncio
async def test_unrefreshed_session_expires_after_365_days_and_old_token_does_not_extend(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    first_refresh, record = await _issue_session(client, db_session, "dev-ttl-expire", "+77015550003")
    issued_at = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
    record.created_at = issued_at
    record.expires_at = issued_at + timedelta(days=365)
    await db_session.commit()

    clock = {"now": issued_at + timedelta(days=100)}
    monkeypatch.setattr("app.api.auth.utcnow", lambda: clock["now"])
    rotated = await client.post("/auth/refresh", json={"refresh_token": first_refresh})
    assert rotated.status_code == 200
    expected_expiry = clock["now"] + timedelta(days=365)
    assert record.expires_at == expected_expiry

    # The rotated-out token is rejected and must not slide the session window.
    clock["now"] = issued_at + timedelta(days=200)
    reused = await client.post("/auth/refresh", json={"refresh_token": first_refresh})
    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"
    assert record.expires_at == expected_expiry

    # Without any further refresh the session ends 365 days after the last one.
    clock["now"] = expected_expiry + timedelta(seconds=1)
    expired = await client.post(
        "/auth/refresh", json={"refresh_token": rotated.json()["refresh_token"]}
    )
    assert expired.status_code == 401
    assert expired.json()["error"]["code"] == "REFRESH_TOKEN_EXPIRED"
    assert record.expires_at == expected_expiry


@pytest.mark.asyncio
async def test_revoked_session_is_not_renewed_on_day_300(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    refresh, record = await _issue_session(client, db_session, "dev-ttl-revoked", "+77015550004")
    issued_at = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
    record.created_at = issued_at
    record.expires_at = issued_at + timedelta(days=365)
    await client.post("/auth/logout", json={"refresh_token": refresh})
    await db_session.refresh(record)
    assert record.revoked_at is not None
    original_expiry = record.expires_at

    monkeypatch.setattr("app.api.auth.utcnow", lambda: issued_at + timedelta(days=300))
    res = await client.post("/auth/refresh", json={"refresh_token": refresh})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"
    assert record.expires_at == original_expiry


@pytest.mark.asyncio
async def test_refresh_token_expired_fails(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Expired refresh token returns 401 REFRESH_TOKEN_EXPIRED."""
    create_res = await client.post("/auth/challenge", json={"device_id": "dev-exp-ref"})
    c_id = create_res.json()["challenge_id"]
    code = create_res.json()["code"]

    await confirm_login_challenge(db_session, code, "+77017772211")

    poll = await client.get(f"/auth/challenge/{c_id}", headers={"X-Device-Id": "dev-exp-ref"})
    raw_refresh = poll.json()["refresh_token"]

    # Manually expire session in DB
    session_record = await db_session.scalar(select(AuthSession))
    assert session_record is not None
    session_record.expires_at = datetime.now(UTC) - timedelta(seconds=10)
    await db_session.commit()

    res = await client.post("/auth/refresh", json={"refresh_token": raw_refresh})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "REFRESH_TOKEN_EXPIRED"


@pytest.mark.asyncio
async def test_refresh_denied_for_deleted_user(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Refresh rotation must not issue tokens for a soft-deleted customer."""
    create_res = await client.post("/auth/challenge", json={"device_id": "dev-del-ref"})
    c_id = create_res.json()["challenge_id"]
    code = create_res.json()["code"]

    await confirm_login_challenge(db_session, code, "+77017772299")
    poll = await client.get(f"/auth/challenge/{c_id}", headers={"X-Device-Id": "dev-del-ref"})
    raw_refresh = poll.json()["refresh_token"]

    user = await db_session.scalar(select(User))
    assert user is not None
    user.deleted_at = datetime.now(UTC)
    await db_session.commit()

    res = await client.post("/auth/refresh", json={"refresh_token": raw_refresh})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "USER_NOT_FOUND"
    assert "access_token" not in res.json()


@pytest.mark.asyncio
async def test_challenge_exchange_denied_for_deleted_user(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """A deleted customer's confirmed challenge cannot be exchanged for tokens."""
    phone = "+77017772288"
    first = await client.post("/auth/challenge", json={"device_id": "dev-del-ex-1"})
    await confirm_login_challenge(db_session, first.json()["code"], phone)
    await client.get(
        f"/auth/challenge/{first.json()['challenge_id']}",
        headers={"X-Device-Id": "dev-del-ex-1"},
    )

    user = await db_session.scalar(select(User).where(User.phone == phone))
    assert user is not None
    user.deleted_at = datetime.now(UTC)
    await db_session.commit()

    second = await client.post("/auth/challenge", json={"device_id": "dev-del-ex-2"})
    await confirm_login_challenge(db_session, second.json()["code"], phone)
    res = await client.get(
        f"/auth/challenge/{second.json()['challenge_id']}",
        headers={"X-Device-Id": "dev-del-ex-2"},
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "ACCOUNT_DEACTIVATED"
