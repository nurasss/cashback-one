import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import AuthSession
from app.services.auth_confirmation import confirm_login_challenge


@pytest.mark.asyncio
async def test_logout_revokes_session_and_blocks_refresh(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """POST /auth/logout revokes session; subsequent refresh requests fail."""
    create_res = await client.post("/auth/challenge", json={"device_id": "dev-logout-1"})
    c_id = create_res.json()["challenge_id"]
    code = create_res.json()["code"]

    await confirm_login_challenge(db_session, code, "+77014443322")

    poll = await client.get(f"/auth/challenge/{c_id}", headers={"X-Device-Id": "dev-logout-1"})
    refresh_token = poll.json()["refresh_token"]

    # Perform logout
    logout_res = await client.post("/auth/logout", json={"refresh_token": refresh_token})
    assert logout_res.status_code == 200
    assert logout_res.json() == {"status": "ok"}

    # Verify session revoked in DB
    session_record = await db_session.scalar(select(AuthSession))
    assert session_record is not None
    assert session_record.revoked_at is not None

    # Refresh must fail with 401
    refresh_res = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_res.status_code == 401
    assert refresh_res.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"

    # Repeated logout must be safe and idempotent
    repeat_res = await client.post("/auth/logout", json={"refresh_token": refresh_token})
    assert repeat_res.status_code == 200
    assert repeat_res.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_logout_one_session_does_not_affect_other_sessions(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Logging out session on Device A leaves session on Device B active."""
    phone = "+77018889900"

    # Device A login
    c1 = (await client.post("/auth/challenge", json={"device_id": "device-A"})).json()
    await confirm_login_challenge(db_session, c1["code"], phone)
    p1 = (await client.get(f"/auth/challenge/{c1['challenge_id']}", headers={"X-Device-Id": "device-A"})).json()
    refresh_a = p1["refresh_token"]

    # Device B login (same phone, different device)
    c2 = (await client.post("/auth/challenge", json={"device_id": "device-B"})).json()
    await confirm_login_challenge(db_session, c2["code"], phone)
    p2 = (await client.get(f"/auth/challenge/{c2['challenge_id']}", headers={"X-Device-Id": "device-B"})).json()
    refresh_b = p2["refresh_token"]

    # Logout Device A
    res_logout_a = await client.post("/auth/logout", json={"refresh_token": refresh_a})
    assert res_logout_a.status_code == 200

    # Device A refresh is rejected
    res_ref_a = await client.post("/auth/refresh", json={"refresh_token": refresh_a})
    assert res_ref_a.status_code == 401

    # Device B refresh continues to work
    res_ref_b = await client.post("/auth/refresh", json={"refresh_token": refresh_b})
    assert res_ref_b.status_code == 200
    assert "access_token" in res_ref_b.json()
