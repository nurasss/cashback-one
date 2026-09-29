"""Tests for independent heartbeat loop."""

import asyncio
from pathlib import Path

import pytest

from poscenter_loyalty_agent.cloud_client import FakeCloudClient
from poscenter_loyalty_agent.config import AgentSettings
from poscenter_loyalty_agent.models import HeartbeatPayload
from poscenter_loyalty_agent.runtime import AgentRuntime
from poscenter_loyalty_agent.source import FakeLoyaltySource
from poscenter_loyalty_agent.state_store import StateStore


@pytest.mark.asyncio
async def test_heartbeat_sends_payload_independently(tmp_path: Path) -> None:
    db_file = tmp_path / "heartbeat_test.db"
    store = StateStore(db_file)
    cloud = FakeCloudClient()
    source = FakeLoyaltySource()

    settings = AgentSettings(
        agent_env="test",
        agent_api_key="test-key-heartbeat",
        agent_state_db_path=db_file,
        agent_heartbeat_interval_seconds=1,
        agent_poll_interval_seconds=10,
        one_adapter_mode="fake",
    )

    runtime = AgentRuntime(
        settings=settings,
        state_store=store,
        cloud_client=cloud,
        source=source,
    )

    # Run heartbeat once manually
    status = store.get_status()
    await cloud.send_heartbeat(
        HeartbeatPayload(
            version=settings.agent_version,
            last_successful_sync_at=status.last_successful_sync_at,
            error=status.last_error,
        )
    )
    assert len(cloud.heartbeats) == 1

    # Simulate heartbeat loop running
    hb_task = asyncio.create_task(runtime._heartbeat_loop())
    await asyncio.sleep(0.1)
    runtime.request_stop()
    await hb_task

    assert len(cloud.heartbeats) >= 1
    updated_status = store.get_status()
    assert updated_status.last_heartbeat_at is not None
