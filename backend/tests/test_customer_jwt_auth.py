import uuid
from datetime import timedelta

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, hash_refresh_token
from app.core.time import utcnow
from app.models.entities import AuthSession, User


async def create_test_customer(
    db_session: AsyncSession,
    phone: str = "+77011112233",
) -> tuple[User, AuthSession, str]:
    """Helper to create a user, active auth session, and valid access token."""
    user = User(phone=phone, language="ru")
    db_session.add(user)
    await db_session.flush()

    raw_refresh = "rfr_dummy_refresh_token_test_12345"
    auth_session = AuthSession(
        user_id=user.id,
        device_id="test-device-uuid",
        refresh_token_hash=hash_refresh_token(raw_refresh),
        expires_at=utcnow() + timedelta(days=30),
    )
    db_session.add(auth_session)
    await db_session.commit()

    token = create_access_token(user_id=user.id, session_id=auth_session.id)
    return user, auth_session, token


@pytest.mark.asyncio
async def test_auth_valid_bearer_token(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Valid Bearer token grants access to customer endpoints."""
    _, _, token = await create_test_customer(db_session)

    response = await client.get(
        "/me/cards",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_auth_missing_header(client: AsyncClient) -> None:
    """Request without Authorization header is rejected with 401."""
    response = await client.get("/me/cards")
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_auth_malformed_header(client: AsyncClient) -> None:
    """Malformed Authorization headers are rejected with 401."""
    for bad_header in ["Bearer", "Basic 12345", "Bearer ", "Bearer a b c", "Token abc"]:
        response = await client.get("/me/cards", headers={"Authorization": bad_header})
        assert response.status_code == 401
        assert response.json()["error"]["code"] in {
            "INVALID_AUTHORIZATION_HEADER",
            "INVALID_TOKEN",
        }


@pytest.mark.asyncio
async def test_auth_expired_access_token(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Expired access token is rejected with 401 TOKEN_EXPIRED."""
    user, auth_session, _ = await create_test_customer(db_session)
    expired_token = create_access_token(
        user_id=user.id,
        session_id=auth_session.id,
        expires_delta_seconds=-10,
    )

    response = await client.get(
        "/me/cards",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_EXPIRED"


@pytest.mark.asyncio
async def test_auth_tampered_signature(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Token with invalid signature is rejected with 401 INVALID_TOKEN."""
    user, auth_session, _ = await create_test_customer(db_session)
    bad_token = jwt.encode(
        {
            "sub": str(user.id),
            "sid": str(auth_session.id),
            "typ": "access",
            "iat": int(utcnow().timestamp()),
            "exp": int((utcnow() + timedelta(hours=1)).timestamp()),
        },
        "wrong_signing_key_at_least_32_characters_long",
        algorithm="HS256",
    )

    response = await client.get(
        "/me/cards",
        headers={"Authorization": f"Bearer {bad_token}"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


@pytest.mark.asyncio
async def test_auth_invalid_payload_claims(client: AsyncClient) -> None:
    """Token with non-UUID or missing claims is rejected with 401."""
    bad_token = jwt.encode(
        {
            "sub": "not-a-uuid",
            "sid": "not-a-uuid",
            "typ": "access",
            "iat": int(utcnow().timestamp()),
            "exp": int((utcnow() + timedelta(hours=1)).timestamp()),
        },
        settings.jwt_signing_key,
        algorithm="HS256",
    )

    response = await client.get(
        "/me/cards",
        headers={"Authorization": f"Bearer {bad_token}"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


@pytest.mark.asyncio
async def test_auth_revoked_session(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Session revoked via logout or admin blocks subsequent access."""
    _, auth_session, token = await create_test_customer(db_session)

    # Revoke session
    auth_session.revoked_at = utcnow()
    await db_session.commit()

    response = await client.get(
        "/me/cards",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_REVOKED"


@pytest.mark.asyncio
async def test_auth_expired_session(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Expired session in database blocks access even if access token is technically valid."""
    _, auth_session, token = await create_test_customer(db_session)

    auth_session.expires_at = utcnow() - timedelta(minutes=1)
    await db_session.commit()

    response = await client.get(
        "/me/cards",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_EXPIRED"


@pytest.mark.asyncio
async def test_auth_session_not_found(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Non-existent session ID in access token returns 401 SESSION_NOT_FOUND."""
    user, _, _ = await create_test_customer(db_session)
    non_existent_sid = uuid.uuid4()
    ghost_token = create_access_token(user_id=user.id, session_id=non_existent_sid)

    response = await client.get(
        "/me/cards",
        headers={"Authorization": f"Bearer {ghost_token}"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"


@pytest.mark.asyncio
async def test_auth_deactivated_user(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Soft-deleted/deactivated customer is denied access with 401."""
    user, _, token = await create_test_customer(db_session)

    user.deleted_at = utcnow()
    await db_session.commit()

    response = await client.get(
        "/me/cards",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "USER_NOT_FOUND"
