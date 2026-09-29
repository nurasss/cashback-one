"""Tests for AgentRuntime sync loop, at-least-once delivery, page limits, and error handling."""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from poscenter_loyalty_agent.cloud_client import (
    CloudProtocolError,
    FakeCloudClient,
)
from poscenter_loyalty_agent.config import AgentSettings
from poscenter_loyalty_agent.models import (
    CardsSyncPayload,
    CardsSyncResult,
    CardSyncItem,
    TransactionSyncItem,
)
from poscenter_loyalty_agent.runtime import AgentRuntime, SourceCursorStalledError
from poscenter_loyalty_agent.source import FakeLoyaltySource, SourceProtocolError
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

    await runtime.sync_cycle()

    assert len(cloud.synced_cards) == 1
    assert len(cloud.synced_cards[0].cards) == 2
    assert len(cloud.synced_transactions) == 1
    assert len(cloud.synced_transactions[0].transactions) == 1

    assert store.get_cursor("cards") == "2"
    assert store.get_cursor("transactions") == "1"
    status = store.get_status()
    assert status.last_successful_sync_at is not None
    assert status.last_error is None


@pytest.mark.asyncio
async def test_real_crash_after_ack_fault_injection(tmp_path: Path) -> None:
    """True at-least-once crash window test via fault injection on StateStore.commit_cursor.

    Verifies Cloud receives batch, commit fails, cursor in SQLite remains None/old,
    and second run with fresh runtime safely re-delivers the batch to Cloud.
    """
    db_file = tmp_path / "crash_fault.db"
    cloud = FakeCloudClient()
    now = datetime(2026, 9, 29, 12, 0, 0, tzinfo=UTC)
    cards = [CardSyncItem(barcode="1000000000001", balance=Decimal("100"), updated_at=now)]
    source = FakeLoyaltySource(cards=cards)

    class InjectedCrash(Exception):
        pass

    class FailingCommitStateStore(StateStore):
        def commit_cursor(self, stream: str, cursor_value: str | None, synced_at: datetime) -> None:
            raise InjectedCrash("Simulated power loss immediately after Cloud ACK")

    failing_store = FailingCommitStateStore(db_file)
    settings = AgentSettings(
        agent_env="test",
        agent_api_key="test-key-crash",
        agent_state_db_path=db_file,
        one_adapter_mode="fake",
    )

    runtime1 = AgentRuntime(
        settings=settings,
        state_store=failing_store,
        cloud_client=cloud,
        source=source,
    )

    # 1. Run sync: Cloud receives batch, but commit_cursor crashes
    with pytest.raises(InjectedCrash):
        await runtime1.sync_cycle()

    # Cloud has received batch 1 time
    assert len(cloud.synced_cards) == 1
    assert cloud.synced_cards[0].cards[0].barcode == "1000000000001"

    # SQLite file persistent cursor is still None (was never committed)
    verify_store = StateStore(db_file)
    assert verify_store.get_cursor("cards") is None

    # 2. Restart agent with normal StateStore and fresh runtime
    fresh_store = StateStore(db_file)
    runtime2 = AgentRuntime(
        settings=settings,
        state_store=fresh_store,
        cloud_client=cloud,
        source=source,
    )

    await runtime2.sync_cycle()

    # Cloud has received batch 2 times (at-least-once delivery demonstrated)
    assert len(cloud.synced_cards) == 2
    # Persistent cursor is now safely committed
    assert fresh_store.get_cursor("cards") == "1"


@pytest.mark.asyncio
async def test_max_pages_per_cycle_and_no_transactions_starvation(tmp_path: Path) -> None:
    """When cards stream hits max_pages_per_cycle, cards cycle ends without error,

    and transactions stream still gets its own full page budget.
    """
    db_file = tmp_path / "page_budget.db"
    store = StateStore(db_file)
    cloud = FakeCloudClient()
    now = datetime(2026, 9, 29, 12, 0, 0, tzinfo=UTC)

    # 25 cards with batch_size=1 -> 25 pages available
    cards = [
        CardSyncItem(barcode=f"10000000000{i:02d}", balance=Decimal("10"), updated_at=now)
        for i in range(25)
    ]
    # 5 transactions with batch_size=1
    transactions = [
        TransactionSyncItem(
            external_id=f"tx-{i}",
            barcode="1000000000000",
            type="accrual",
            amount=Decimal("5"),
            balance_after=Decimal("15"),
            occurred_at=now,
        )
        for i in range(5)
    ]
    source = FakeLoyaltySource(cards=cards, transactions=transactions)

    settings = AgentSettings(
        agent_env="test",
        agent_api_key="test-key-pages",
        agent_state_db_path=db_file,
        agent_card_batch_size=1,
        agent_tx_batch_size=1,
        agent_max_pages_per_cycle=10,  # Max 10 pages per cycle
        one_adapter_mode="fake",
    )

    runtime = AgentRuntime(
        settings=settings,
        state_store=store,
        cloud_client=cloud,
        source=source,
    )

    # First cycle: cards should process 10 pages, transactions should process 5 pages
    await runtime.sync_cycle()

    assert len(cloud.synced_cards) == 10
    assert store.get_cursor("cards") == "10"
    # Reaching page budget is NOT an error
    status = store.get_status()
    assert status.last_error is None

    # Transactions stream was NOT starved: all 5 processed
    assert len(cloud.synced_transactions) == 5
    assert store.get_cursor("transactions") == "5"

    # Second cycle: resumes from cards cursor 10 -> processes next 10 (up to 20)
    await runtime.sync_cycle()
    assert len(cloud.synced_cards) == 20
    assert store.get_cursor("cards") == "20"


@pytest.mark.asyncio
async def test_empty_page_with_more_raises_source_protocol_error(tmp_path: Path) -> None:
    """If source returns items=[] with has_more=True, runtime raises SourceProtocolError

    without advancing cursor or calling Cloud API.
    """
    db_file = tmp_path / "empty_page.db"
    store = StateStore(db_file)
    cloud = FakeCloudClient()

    now = datetime(2026, 9, 29, 12, 0, 0, tzinfo=UTC)
    cards = [CardSyncItem(barcode="1000000000001", balance=Decimal("100"), updated_at=now)]
    source = FakeLoyaltySource(cards=cards)
    source.simulate_empty_page_with_more_on_cards = True

    settings = AgentSettings(
        agent_env="test",
        agent_api_key="test-key-empty",
        agent_state_db_path=db_file,
        one_adapter_mode="fake",
    )

    runtime = AgentRuntime(
        settings=settings,
        state_store=store,
        cloud_client=cloud,
        source=source,
    )

    with pytest.raises(SourceProtocolError, match="SOURCE_PROTOCOL_ERROR"):
        await runtime.sync_cycle()

    # Zero Cloud requests sent
    assert len(cloud.synced_cards) == 0
    # Cursor unchanged
    assert store.get_cursor("cards") is None


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

    with pytest.raises(SourceCursorStalledError, match="SOURCE_CURSOR_STALLED"):
        await runtime.sync_cycle()


@pytest.mark.asyncio
async def test_cloud_protocol_error_retry_and_cursor_unchanged(tmp_path: Path) -> None:
    """When CloudProtocolError is encountered, sync loop backs off and cursor remains uncommitted."""
    db_file = tmp_path / "proto_err.db"
    store = StateStore(db_file)
    class FailingProtoCloud(FakeCloudClient):
        async def sync_cards(self, payload: CardsSyncPayload) -> CardsSyncResult:
            raise CloudProtocolError("CLOUD_PROTOCOL_ERROR: Invalid 2xx JSON")

    cloud = FailingProtoCloud()

    now = datetime(2026, 9, 29, 12, 0, 0, tzinfo=UTC)
    cards = [CardSyncItem(barcode="1000000000001", balance=Decimal("100"), updated_at=now)]
    source = FakeLoyaltySource(cards=cards)

    slept_delays: list[float] = []

    async def fake_sleep(d: float) -> None:
        slept_delays.append(d)
        runtime.request_stop()

    settings = AgentSettings(
        agent_env="test",
        agent_api_key="test-key-proto",
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

    await runtime._sync_loop()

    status = store.get_status()
    assert status.last_error is not None
    assert "CLOUD_PROTOCOL_ERROR" in status.last_error
    assert store.get_cursor("cards") is None
    assert len(slept_delays) >= 1


@pytest.mark.asyncio
async def test_graceful_shutdown_finishes_inflight_operation(tmp_path: Path) -> None:
    """In-flight sync operation is allowed to complete within shutdown grace period."""
    db_file = tmp_path / "shutdown_grace.db"
    store = StateStore(db_file)
    now = datetime(2026, 9, 29, 12, 0, 0, tzinfo=UTC)
    cards = [CardSyncItem(barcode="1000000000001", balance=Decimal("100"), updated_at=now)]
    source = FakeLoyaltySource(cards=cards)

    cloud_sync_started = asyncio.Event()

    class SlowCloudClient(FakeCloudClient):
        async def sync_cards(self, payload: CardsSyncPayload) -> CardsSyncResult:
            cloud_sync_started.set()
            await asyncio.sleep(0.05)  # Completes well within 5.0s grace
            return await super().sync_cards(payload)

    cloud = SlowCloudClient()
    settings = AgentSettings(
        agent_env="test",
        agent_api_key="test-key-grace",
        agent_state_db_path=db_file,
        agent_shutdown_grace_seconds=5.0,
        one_adapter_mode="fake",
    )

    runtime = AgentRuntime(settings=settings, state_store=store, cloud_client=cloud, source=source)

    run_task = asyncio.create_task(runtime.run())
    await cloud_sync_started.wait()

    # Request stop while in-flight
    runtime.request_stop()
    await run_task

    # In-flight sync finished and committed cursor
    assert store.get_cursor("cards") == "1"
    assert len(cloud.synced_cards) == 1


@pytest.mark.asyncio
async def test_graceful_shutdown_bounded_cancel_on_hung_operation(tmp_path: Path) -> None:
    """Hung operation exceeding shutdown grace period is forcibly cancelled in bounded time."""
    db_file = tmp_path / "shutdown_hung.db"
    store = StateStore(db_file)
    now = datetime(2026, 9, 29, 12, 0, 0, tzinfo=UTC)
    cards = [CardSyncItem(barcode="1000000000001", balance=Decimal("100"), updated_at=now)]
    source = FakeLoyaltySource(cards=cards)

    sync_hung = asyncio.Event()

    class HungCloudClient(FakeCloudClient):
        async def sync_cards(self, payload: CardsSyncPayload) -> CardsSyncResult:
            sync_hung.set()
            await asyncio.sleep(100.0)  # Hangs indefinitely
            return await super().sync_cards(payload)

    cloud = HungCloudClient()
    settings = AgentSettings(
        agent_env="test",
        agent_api_key="test-key-hung",
        agent_state_db_path=db_file,
        agent_shutdown_grace_seconds=0.1,  # Short 100ms grace period
        one_adapter_mode="fake",
    )

    runtime = AgentRuntime(settings=settings, state_store=store, cloud_client=cloud, source=source)

    run_task = asyncio.create_task(runtime.run())
    await sync_hung.wait()

    start_time = asyncio.get_running_loop().time()
    runtime.request_stop()
    await run_task
    elapsed = asyncio.get_running_loop().time() - start_time

    # Bounded termination: stopped well before 100s
    assert elapsed < 1.0
    # Cursor was NOT committed
    assert store.get_cursor("cards") is None
