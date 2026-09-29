"""Tests for AgentRuntime sync loop, at-least-once delivery, and error handling."""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from poscenter_loyalty_agent.cloud_client import CloudRetryableError, FakeCloudClient
from poscenter_loyalty_agent.config import AgentSettings
from poscenter_loyalty_agent.models import (
    CardsSyncPayload,
    CardsSyncResult,
    CardSyncItem,
    TransactionSyncItem,
)
from poscenter_loyalty_agent.runtime import AgentRuntime, SourceCursorStalledError
from poscenter_loyalty_agent.source import FakeLoyaltySource
from poscenter_loyalty_agent.state_store import StateStore


@pytest.mark.asyncio
async def test_full_sync_cycle(tmp_path: Path) -> None:
    db_file = tmp_path / "sync_test.db"
    store = StateStore(db_file)
    cloud = FakeCloudClient()

    now = datetime(2026, 9, 29, 12, 0, 0, tzinfo=UTC)
    cards = [
        CardSyncItem(barcode="1000000000001", balance=Decimal("100"), updated_at=now),
        CardSyncItem(barcode="1000000000002", balance=Decimal("200"), updated_at=now),
    ]
    transactions = [
        TransactionSyncItem(
            external_id="tx-001",
            barcode="1000000000001",
            type="accrual",
            amount=Decimal("50"),
            balance_after=Decimal("150"),
            occurred_at=now,
        )
    ]
    source = FakeLoyaltySource(cards=cards, transactions=transactions)

    settings = AgentSettings(
        agent_env="test",
        agent_api_key="test-key-sync",
        agent_state_db_path=db_file,
        agent_card_batch_size=10,
        agent_tx_batch_size=10,
        one_adapter_mode="fake",
    )

    runtime = AgentRuntime(
        settings=settings,
        state_store=store,
        cloud_client=cloud,
        source=source,
    )

    # Execute one cycle
    await runtime.sync_cycle()

    # Cloud received items
    assert len(cloud.synced_cards) == 1
    assert len(cloud.synced_cards[0].cards) == 2
    assert len(cloud.synced_transactions) == 1
    assert len(cloud.synced_transactions[0].transactions) == 1

    # State store committed cursors
    assert store.get_cursor("cards") == "2"
    assert store.get_cursor("transactions") == "1"
    status = store.get_status()
    assert status.last_successful_sync_at is not None
    assert status.last_error is None


@pytest.mark.asyncio
async def test_at_least_once_delivery_crash_before_cursor_commit(tmp_path: Path) -> None:
    """If cloud ACK succeeds, but checkpoint write fails / restarts before commit,

    the batch will be re-sent on next run (at-least-once).
    """
    db_file = tmp_path / "crash_test.db"
    store = StateStore(db_file)
    cloud = FakeCloudClient()

    now = datetime(2026, 9, 29, 12, 0, 0, tzinfo=UTC)
    cards = [CardSyncItem(barcode="1000000000001", balance=Decimal("100"), updated_at=now)]
    source = FakeLoyaltySource(cards=cards)

    settings = AgentSettings(
        agent_env="test",
        agent_api_key="test-key-crash",
        agent_state_db_path=db_file,
        one_adapter_mode="fake",
    )

    runtime = AgentRuntime(
        settings=settings,
        state_store=store,
        cloud_client=cloud,
        source=source,
    )

    # Simulate: Cloud syncs cards, but SQLite cursor commit was not reached
    await cloud.sync_cards(CardsSyncPayload(cards=cards))
    # Cursor was NOT committed in store
    assert store.get_cursor("cards") is None

    # Next run starts with None cursor and safely resends
    await runtime.sync_cycle()
    assert store.get_cursor("cards") == "1"


@pytest.mark.asyncio
async def test_stalled_cursor_detection(tmp_path: Path) -> None:
    db_file = tmp_path / "stalled_test.db"
    store = StateStore(db_file)
    cloud = FakeCloudClient()

    now = datetime(2026, 9, 29, 12, 0, 0, tzinfo=UTC)
    cards = [CardSyncItem(barcode="1000000000001", balance=Decimal("100"), updated_at=now)]
    source = FakeLoyaltySource(cards=cards)
    source.simulate_stalled_cursor_on_cards = True

    settings = AgentSettings(
        agent_env="test",
        agent_api_key="test-key-stalled",
        agent_state_db_path=db_file,
        one_adapter_mode="fake",
    )

    runtime = AgentRuntime(
        settings=settings,
        state_store=store,
        cloud_client=cloud,
        source=source,
    )

    # Must raise SourceCursorStalledError instead of spinning infinitely
    with pytest.raises(SourceCursorStalledError, match="SOURCE_CURSOR_STALLED"):
        await runtime.sync_cycle()


@pytest.mark.asyncio
async def test_sync_loop_retry_on_cloud_temporary_error(tmp_path: Path) -> None:
    db_file = tmp_path / "retry_loop_test.db"
    store = StateStore(db_file)
    class FailingCloud(FakeCloudClient):
        async def sync_cards(self, payload: CardsSyncPayload) -> CardsSyncResult:
            raise CloudRetryableError("503 Gateway Timeout")

    cloud = FailingCloud()

    now = datetime(2026, 9, 29, 12, 0, 0, tzinfo=UTC)
    cards = [CardSyncItem(barcode="1000000000001", balance=Decimal("100"), updated_at=now)]
    source = FakeLoyaltySource(cards=cards)

    slept_delays: list[float] = []

    async def fake_sleep(d: float) -> None:
        slept_delays.append(d)

    settings = AgentSettings(
        agent_env="test",
        agent_api_key="test-key-retry",
        agent_state_db_path=db_file,
        one_adapter_mode="fake",
    )

    runtime = AgentRuntime(
        settings=settings,
        state_store=store,
        cloud_client=cloud,
        source=source,
        sleep_fn=fake_sleep,
    )

    sync_task = asyncio.create_task(runtime._sync_loop())
    await asyncio.sleep(0.05)
    runtime.request_stop()
    await sync_task

    status = store.get_status()
    assert status.last_error is not None
    assert "503 Gateway Timeout" in status.last_error
    assert len(slept_delays) >= 1
