"""Tests for independent heartbeat loop."""

import asyncio
from pathlib import Path
from typing import Any

import pytest

from poscenter_loyalty_agent.cloud_client import FakeCloudClient
from poscenter_loyalty_agent.config import AgentSettings
from poscenter_loyalty_agent.runtime import AgentRuntime
from poscenter_loyalty_agent.source import FakeLoyaltySource
from poscenter_loyalty_agent.state_store import StateStore


@pytest.mark.asyncio
async def test_heartbeat_fires_independently_during_sync_backoff(tmp_path: Path) -> None:
    """Heartbeat must fire and record status even when the sync loop is backing off."""
    db_file = tmp_path / "heartbeat_backoff.db"
    store = StateStore(db_file)
    cloud = FakeCloudClient()

    class BrokenSource(FakeLoyaltySource):
        async def fetch_cards(self, cursor: str | None, limit: int) -> Any:
            raise RuntimeError("1C Connection dropped")

    source = BrokenSource()

    sync_slept_event = asyncio.Event()

    async def fake_sleep(seconds: float) -> None:
        sync_slept_event.set()
        await asyncio.sleep(10)

    settings = AgentSettings(
        agent_env="test",
        agent_api_key="test-key-heartbeat",
        agent_state_db_path=db_file,
        agent_heartbeat_interval_seconds=1,  # Short heartbeat interval
        agent_poll_interval_seconds=10,
        one_adapter_mode="fake",
    )

    runtime = AgentRuntime(
        settings=settings,
        state_store=store,
        cloud_client=cloud,
        source=source,
        sleep_fn=fake_sleep,
    )

    # Start both loops concurrently via run()
    run_task = asyncio.create_task(runtime.run())

    # Wait until sync loop hits error and enters backoff
    await sync_slept_event.wait()

    # Wait for heartbeat loop to fire during sync backoff and transmit the error
    for _ in range(30):
        if any(hb.error is not None for hb in cloud.heartbeats):
            break
        await asyncio.sleep(0.05)

    runtime.request_stop()
    await run_task

    # Verify heartbeat ran and transmitted the sync error
    assert len(cloud.heartbeats) >= 1
    last_hb = cloud.heartbeats[-1]
    assert last_hb.version == settings.agent_version
    assert "1C Connection dropped" in str(last_hb.error)

    # State store updated
    status = store.get_status()
    assert status.last_heartbeat_at is not None
    assert status.last_error is not None
