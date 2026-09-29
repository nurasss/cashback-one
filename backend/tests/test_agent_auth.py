import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Agent, Business
from app.services.agent_auth import (
    hash_agent_key,
    issue_agent_key,
    revoke_agent,
    rotate_agent_key,
)


@pytest.mark.asyncio
async def test_agent_auth_missing_key(client: AsyncClient) -> None:
    response = await client.post("/agent/heartbeat", json={})
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "AGENT_KEY_MISSING"


@pytest.mark.asyncio
async def test_agent_auth_invalid_key(client: AsyncClient) -> None:
    response = await client.post(
        "/agent/heartbeat",
        headers={"X-Agent-Key": "agk_invalid_key_12345"},
        json={},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "AGENT_KEY_INVALID"


@pytest.mark.asyncio
async def test_agent_auth_valid_key(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    biz = Business(name="Auth Test Biz")
    db_session.add(biz)
    await db_session.commit()

    _agent, raw_key = await issue_agent_key(db_session, biz.id, version="1.0.0")
    await db_session.commit()

    # Using X-Agent-Key header
    response = await client.post(
        "/agent/heartbeat",
        headers={"X-Agent-Key": raw_key},
        json={"version": "1.0.1"},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Using Authorization: Bearer <key> header
    bearer_response = await client.post(
        "/agent/heartbeat",
        headers={"Authorization": f"Bearer {raw_key}"},
        json={"version": "1.0.2"},
    )
    assert bearer_response.status_code == 200
    assert bearer_response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_agent_auth_revoked_agent(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    biz = Business(name="Revoke Test Biz")
    db_session.add(biz)
    await db_session.commit()

    agent, raw_key = await issue_agent_key(db_session, biz.id)
    await db_session.commit()

    await revoke_agent(db_session, agent)
    await db_session.commit()

    response = await client.post(
        "/agent/heartbeat",
        headers={"X-Agent-Key": raw_key},
        json={},
    )
    assert response.status_code == 403
    data = response.json()
    assert data["error"]["code"] == "AGENT_REVOKED"


@pytest.mark.asyncio
async def test_plaintext_key_not_stored_in_db(db_session: AsyncSession) -> None:
    biz = Business(name="Crypto Test Biz")
    db_session.add(biz)
    await db_session.commit()

    agent, raw_key = await issue_agent_key(db_session, biz.id)
    await db_session.commit()

    # Ensure DB only stores SHA-256 hash
    stored_agent = await db_session.scalar(select(Agent).where(Agent.id == agent.id))
    assert stored_agent is not None
    assert stored_agent.key_hash != raw_key
    assert stored_agent.key_hash == hash_agent_key(raw_key)


@pytest.mark.asyncio
async def test_agent_key_rotation(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    biz = Business(name="Rotation Test Biz")
    db_session.add(biz)
    await db_session.commit()

    agent, old_key = await issue_agent_key(db_session, biz.id)
    await db_session.commit()

    new_key = await rotate_agent_key(db_session, agent)
    await db_session.commit()

    assert new_key != old_key

    # Old key must be rejected
    old_res = await client.post(
        "/agent/heartbeat",
        headers={"X-Agent-Key": old_key},
        json={},
    )
    assert old_res.status_code == 401

    # New key must be accepted
    new_res = await client.post(
        "/agent/heartbeat",
        headers={"X-Agent-Key": new_key},
        json={},
    )
    assert new_res.status_code == 200
