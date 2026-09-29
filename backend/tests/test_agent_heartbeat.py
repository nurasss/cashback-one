from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Agent, Business
from app.services.agent_auth import issue_agent_key


@pytest.mark.asyncio
async def test_heartbeat_updates_status_and_server_time(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    biz = Business(name="Heartbeat Biz")
    db_session.add(biz)
    await db_session.commit()

    agent, key = await issue_agent_key(db_session, biz.id, version="0.9.0")
    await db_session.commit()

    before_call = datetime.now(UTC)
    sync_time = datetime(2026, 9, 29, 9, 30, 0, tzinfo=UTC)

    response = await client.post(
        "/agent/heartbeat",
        headers={"X-Agent-Key": key},
        json={
            "version": "1.2.0",
            "last_successful_sync_at": sync_time.isoformat(),
            "error": "Temporary 1C COM lock, resolved",
        },
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    after_call = datetime.now(UTC)

    # Check updated fields in DB
    refreshed_agent = await db_session.scalar(select(Agent).where(Agent.id == agent.id))
    assert refreshed_agent is not None
    assert refreshed_agent.version == "1.2.0"
    assert refreshed_agent.last_sync_at is not None
    assert refreshed_agent.last_error == "Temporary 1C COM lock, resolved"
    # Verify server time: last_seen_at must be set between before_call and after_call
    assert refreshed_agent.last_seen_at is not None
    assert before_call <= refreshed_agent.last_seen_at <= after_call


@pytest.mark.asyncio
async def test_heartbeat_nullable_error(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    biz = Business(name="Heartbeat Nullable Error Biz")
    db_session.add(biz)
    await db_session.commit()

    agent, key = await issue_agent_key(db_session, biz.id)
    await db_session.commit()

    response = await client.post(
        "/agent/heartbeat",
        headers={"X-Agent-Key": key},
        json={
            "version": "1.0.0",
            "last_successful_sync_at": None,
            "error": None,
        },
    )
    assert response.status_code == 200

    refreshed_agent = await db_session.scalar(select(Agent).where(Agent.id == agent.id))
    assert refreshed_agent is not None
    assert refreshed_agent.last_error is None
    assert refreshed_agent.last_sync_at is None
