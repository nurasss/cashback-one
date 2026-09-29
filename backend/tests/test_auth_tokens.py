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
