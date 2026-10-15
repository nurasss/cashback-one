import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    CHALLENGE_CODE_ALPHABET,
    CHALLENGE_CODE_LENGTH,
    generate_challenge_code,
    hash_challenge_code,
)
from app.models.entities import LoginChallenge
from app.services.auth_confirmation import confirm_login_challenge


def test_challenge_code_properties() -> None:
    """Challenge code must be 8 chars, safe alphabet, no ambiguous characters."""
    code = generate_challenge_code()
    assert len(code) == CHALLENGE_CODE_LENGTH
    for char in code:
        assert char in CHALLENGE_CODE_ALPHABET
        assert char not in {"0", "O", "1", "I", "L", "l"}


def test_challenge_code_hmac_deterministic() -> None:
    """HMAC-SHA256 must be deterministic for identical codes regardless of case/whitespace."""
    code = "23456789"
    digest1 = hash_challenge_code(code)
    digest2 = hash_challenge_code("  23456789 ")
    assert digest1 == digest2
    assert len(digest1) == 64


@pytest.mark.asyncio
async def test_create_challenge_success(client: AsyncClient, db_session: AsyncSession) -> None:
    """POST /auth/challenge creates challenge, returns code and wa.me URL, plaintext code not in DB."""
    device_id = "test-device-uuid-12345"
    response = await client.post(
        "/auth/challenge",
        json={"device_id": device_id},
    )
    assert response.status_code == 200
    data = response.json()

    assert "challenge_id" in data
    assert "code" in data
    assert len(data["code"]) == 8
    assert "login_url" in data
    assert data["expires_in"] == 180

    # Validate wa.me URL structure
    assert "https://wa.me/77001234567?text=" in data["login_url"]
    assert data["code"] in data["login_url"]

    # Verify plaintext code is NOT stored in database
    challenge = await db_session.scalar(
        select(LoginChallenge).where(LoginChallenge.id == uuid.UUID(data["challenge_id"]))
    )
    assert challenge is not None

    assert challenge.code_hash != data["code"]
    assert challenge.code_hash == hash_challenge_code(data["code"])
    assert challenge.device_id == device_id
    assert challenge.status == "pending"


@pytest.mark.asyncio
async def test_create_challenge_invalid_device_rejected(client: AsyncClient) -> None:
    """POST /auth/challenge with empty or whitespace-only device_id must be rejected with 422."""
    res1 = await client.post("/auth/challenge", json={"device_id": ""})
    assert res1.status_code == 422

    res2 = await client.post("/auth/challenge", json={"device_id": "   "})
    assert res2.status_code == 422


@pytest.mark.asyncio
async def test_create_challenge_device_id_normalized(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """POST /auth/challenge strips whitespace and stores normalized device_id."""
    res = await client.post("/auth/challenge", json={"device_id": "  padded-device-id  "})
    assert res.status_code == 200
    cid = res.json()["challenge_id"]

    challenge = await db_session.get(LoginChallenge, uuid.UUID(cid))
    assert challenge is not None
    assert challenge.device_id == "padded-device-id"

    # Status check with padded header also matches normalized device_id
    poll = await client.get(f"/auth/challenge/{cid}", headers={"X-Device-Id": " padded-device-id "})
    assert poll.status_code == 200


@pytest.mark.asyncio
async def test_create_challenge_collision_retry_success(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If challenge code collides, the retry loop generates a new code and succeeds."""
    # Create an initial challenge with a known code
    init_res = await client.post("/auth/challenge", json={"device_id": "dev-col-1"})
    colliding_code = init_res.json()["code"]

    attempts = 0
    from app.api import auth

    def mock_generate_code() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return colliding_code  # Force collision on 1st attempt
        return generate_challenge_code()  # Unique code on subsequent attempts

    monkeypatch.setattr(auth, "generate_challenge_code", mock_generate_code)

    res = await client.post("/auth/challenge", json={"device_id": "dev-col-2"})
    assert res.status_code == 200
    assert attempts >= 2
    assert res.json()["code"] != colliding_code


@pytest.mark.asyncio
async def test_create_challenge_collision_exhausted_500(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If 5 consecutive collisions occur, a controlled 500 error is returned."""
    init_res = await client.post("/auth/challenge", json={"device_id": "dev-exhaust-1"})
    colliding_code = init_res.json()["code"]

    from app.api import auth

    monkeypatch.setattr(auth, "generate_challenge_code", lambda: colliding_code)

    res = await client.post("/auth/challenge", json={"device_id": "dev-exhaust-2"})
    assert res.status_code == 500
    assert res.json()["error"]["code"] == "CHALLENGE_GENERATION_FAILED"


@pytest.mark.asyncio
async def test_challenge_status_pending(client: AsyncClient) -> None:
    """GET /auth/challenge/{id} returns status pending while waiting for WhatsApp code."""
    device_id = "device-status-pending-1"
    create_res = await client.post("/auth/challenge", json={"device_id": device_id})
    challenge_id = create_res.json()["challenge_id"]

    res = await client.get(
        f"/auth/challenge/{challenge_id}",
        headers={"X-Device-Id": device_id},
    )
    assert res.status_code == 200
    assert res.json() == {"status": "pending"}


@pytest.mark.asyncio
async def test_challenge_status_device_mismatch_rejected(client: AsyncClient) -> None:
    """GET /auth/challenge/{id} with wrong device_id returns 403 DEVICE_MISMATCH."""
    create_res = await client.post("/auth/challenge", json={"device_id": "device-owner-1"})
    challenge_id = create_res.json()["challenge_id"]

    res = await client.get(
        f"/auth/challenge/{challenge_id}",
        headers={"X-Device-Id": "device-impostor-2"},
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "DEVICE_MISMATCH"


@pytest.mark.asyncio
async def test_challenge_status_missing_device_header_rejected(client: AsyncClient) -> None:
    """GET /auth/challenge/{id} without X-Device-Id header returns 400."""
    create_res = await client.post("/auth/challenge", json={"device_id": "device-owner-1"})
    challenge_id = create_res.json()["challenge_id"]

    res = await client.get(f"/auth/challenge/{challenge_id}")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "DEVICE_HEADER_MISSING"


@pytest.mark.asyncio
async def test_challenge_status_unknown_id_404(client: AsyncClient) -> None:
    """GET /auth/challenge/{id} with non-existent UUID returns 404."""
    import uuid

    res = await client.get(
        f"/auth/challenge/{uuid.uuid4()}",
        headers={"X-Device-Id": "device-any"},
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "CHALLENGE_NOT_FOUND"


@pytest.mark.asyncio
async def test_challenge_status_expired(client: AsyncClient, db_session: AsyncSession) -> None:
    """GET /auth/challenge/{id} returns status expired if TTL elapsed."""
    device_id = "device-expired-1"
    create_res = await client.post("/auth/challenge", json={"device_id": device_id})
    challenge_id = create_res.json()["challenge_id"]

    # Manually expire the challenge in DB
    challenge = await db_session.get(LoginChallenge, uuid.UUID(challenge_id))
    assert challenge is not None

    challenge.expires_at = datetime.now(UTC) - timedelta(seconds=10)
    await db_session.commit()

    res = await client.get(
        f"/auth/challenge/{challenge_id}",
        headers={"X-Device-Id": device_id},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "expired"


@pytest.mark.asyncio
async def test_challenge_confirmed_in_time_exchangeable_after_ttl(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Challenge confirmed before TTL still issues tokens when polled after TTL elapsed."""
    device_id = "device-late-poll-1"
    create_res = await client.post("/auth/challenge", json={"device_id": device_id})
    challenge_id = create_res.json()["challenge_id"]
    code = create_res.json()["code"]

    confirmed = await confirm_login_challenge(db_session, code, "+77019998877")
    assert confirmed.is_success is True

    # Challenge TTL elapses between confirmation and the app's next poll
    challenge = await db_session.get(LoginChallenge, uuid.UUID(challenge_id))
    assert challenge is not None
    challenge.expires_at = datetime.now(UTC) - timedelta(seconds=10)
    await db_session.commit()

    res = await client.get(
        f"/auth/challenge/{challenge_id}",
        headers={"X-Device-Id": device_id},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "confirmed"
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_challenge_confirmed_exchange_window_elapsed_expires(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Confirmed challenge not exchanged within the exchange window expires without tokens."""
    device_id = "device-late-poll-2"
    create_res = await client.post("/auth/challenge", json={"device_id": device_id})
    challenge_id = create_res.json()["challenge_id"]
    code = create_res.json()["code"]

    confirmed = await confirm_login_challenge(db_session, code, "+77019998877")
    assert confirmed.is_success is True

    challenge = await db_session.get(LoginChallenge, uuid.UUID(challenge_id))
    assert challenge is not None
    challenge.confirmed_at = datetime.now(UTC) - timedelta(
        seconds=settings.challenge_exchange_ttl_seconds + 10
    )
    challenge.expires_at = datetime.now(UTC) - timedelta(seconds=10)
    await db_session.commit()

    res = await client.get(
        f"/auth/challenge/{challenge_id}",
        headers={"X-Device-Id": device_id},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "expired"
    assert "access_token" not in data

    await db_session.refresh(challenge)
    assert challenge.status == "expired"


@pytest.mark.asyncio
async def test_challenge_single_use_consumed_cannot_issue_second_session(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Confirmed challenge can be exchanged for tokens once. Second poll returns 409."""
    device_id = "device-single-use-1"
    create_res = await client.post("/auth/challenge", json={"device_id": device_id})
    challenge_id = create_res.json()["challenge_id"]
    code = create_res.json()["code"]

    # Confirm via internal service
    confirmed = await confirm_login_challenge(db_session, code, "+77019998877")
    assert confirmed.is_success is True

    # First polling exchange -> tokens issued
    poll_1 = await client.get(
        f"/auth/challenge/{challenge_id}",
        headers={"X-Device-Id": device_id},
    )
    assert poll_1.status_code == 200
    data_1 = poll_1.json()
    assert data_1["status"] == "confirmed"
    assert "access_token" in data_1
    assert "refresh_token" in data_1

    # Second polling exchange -> must be rejected with 409 CHALLENGE_ALREADY_CONSUMED
    poll_2 = await client.get(
        f"/auth/challenge/{challenge_id}",
        headers={"X-Device-Id": device_id},
    )
    assert poll_2.status_code == 409
    assert poll_2.json()["error"]["code"] == "CHALLENGE_ALREADY_CONSUMED"

