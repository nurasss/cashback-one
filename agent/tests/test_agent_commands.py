from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest

from poscenter_loyalty_agent.cloud_client import (
    CloudRetryableError,
    FakeCloudClient,
    HttpCloudClient,
)
from poscenter_loyalty_agent.config import AgentSettings
from poscenter_loyalty_agent.models import (
    AgentCommandItem,
    AgentCommandsClaimResult,
    CardSyncItem,
    TransactionSyncItem,
)
from poscenter_loyalty_agent.one_com_source import OneComLoyaltySource
from poscenter_loyalty_agent.one_cursor import (
    TxDoneCursor,
    decode_cards_cursor,
    encode_tx_done_cursor,
    is_cursor_ahead_or_equal,
)
from poscenter_loyalty_agent.one_mapping import OneMappingConfig
from poscenter_loyalty_agent.runtime import AgentRuntime
from poscenter_loyalty_agent.source import FakeLoyaltySource, SourceProtocolError
from poscenter_loyalty_agent.state_store import StateStore

# ---------------------------------------------------------------------------
# 1. Claim 404 Handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_claim_404_handled_quietly_without_error() -> None:
    """If server returns 404 (old server), claim_commands returns empty list and logs at DEBUG, without error."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/agent/commands/claim":
            return httpx.Response(404, text="Not Found")
        return httpx.Response(200, json={"status": "ok"})

    transport = httpx.MockTransport(handler)
    client = HttpCloudClient(
        base_url="https://api.cashback-qr.poscenter.kz",
        api_key="test-api-key-12345678",
    )
    client._client = httpx.AsyncClient(
        transport=transport,
        base_url="https://api.cashback-qr.poscenter.kz",
        headers={"X-Agent-Key": "test-api-key-12345678"},
    )

    try:
        res = await client.claim_commands()
        assert isinstance(res, AgentCommandsClaimResult)
        assert res.commands == []
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# 2. sync_now command execution
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_now_wakes_loop_and_completes(tmp_path: Path) -> None:
    """sync_now command immediately triggers a sync pass and reports completion."""
    db_file = tmp_path / "sync_now.db"
    store = StateStore(db_file)
    cloud = FakeCloudClient()

    now = datetime(2026, 11, 6, 12, 0, 0, tzinfo=UTC)
    cards = [CardSyncItem(barcode="1000000000001", balance=Decimal("100"), updated_at=now)]
    txs = [
        TransactionSyncItem(
            external_id="tx-001",
            barcode="1000000000001",
            type="accrual",
            amount=Decimal("50"),
            balance_after=Decimal("150"),
            occurred_at=now,
        )
    ]
    source = FakeLoyaltySource(cards=cards, transactions=txs)

    settings = AgentSettings(
        agent_env="test",
        agent_api_key="test-key-sync-now",
        agent_state_db_path=db_file,
        agent_poll_interval_seconds=60,
    )

    runtime = AgentRuntime(
        settings=settings,
        state_store=store,
        cloud_client=cloud,
        source=source,
    )

    cmd = AgentCommandItem(id="cmd-123", type="sync_now")
    runtime._pending_commands.append(cmd)

    async def stop_after_completion() -> None:
        for _ in range(50):
            await asyncio.sleep(0.05)
            if cloud.completed_commands:
                break
        runtime.request_stop()

    stop_task = asyncio.create_task(stop_after_completion())
    await runtime.run()
    await stop_task

    assert len(cloud.completed_commands) == 1
    cmd_id, status, err = cloud.completed_commands[0]
    assert cmd_id == "cmd-123"
    assert status == "completed"
    assert err is None

    assert len(cloud.synced_cards) >= 1
    assert len(cloud.synced_transactions) >= 1


# ---------------------------------------------------------------------------
# 3. full_resync: sends all cards, initial history, and no cursor rollback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_resync_sends_all_cards_and_no_cursor_rollback(tmp_path: Path) -> None:
    """full_resync sends all cards and txs from beginning and ensures cursor does not roll back."""
    db_file = tmp_path / "full_resync.db"
    store = StateStore(db_file)
    cloud = FakeCloudClient()

    now = datetime(2026, 11, 6, 12, 0, 0, tzinfo=UTC)
    cards = [
        CardSyncItem(barcode="1000000000001", balance=Decimal("100"), updated_at=now),
        CardSyncItem(barcode="1000000000002", balance=Decimal("200"), updated_at=now),
    ]
    txs = [
        TransactionSyncItem(
            external_id="tx-001",
            barcode="1000000000001",
            type="accrual",
            amount=Decimal("50"),
            balance_after=Decimal("150"),
            occurred_at=now,
        )
    ]
    source = FakeLoyaltySource(cards=cards, transactions=txs)

    settings = AgentSettings(
        agent_env="test",
        agent_api_key="test-key-full-resync",
        agent_state_db_path=db_file,
        agent_poll_interval_seconds=60,
    )

    runtime = AgentRuntime(
        settings=settings,
        state_store=store,
        cloud_client=cloud,
        source=source,
    )

    # 1. Normal sync first
    await runtime.sync_cycle(full_resync=False)
    assert len(cloud.synced_cards) == 1
    assert len(cloud.synced_cards[0].cards) == 2
    assert store.get_cursor("cards") == "2"
    assert store.get_cursor("transactions") == "1"

    # 2. Subsequent normal cycle produces 0 new cards
    cloud.synced_cards.clear()
    cloud.synced_transactions.clear()
    await runtime.sync_cycle(full_resync=False)
    assert len(cloud.synced_cards) == 0

    # 3. Full resync command executed
    cmd = AgentCommandItem(id="cmd-full", type="full_resync")
    runtime._pending_commands.append(cmd)

    async def stop_after_full() -> None:
        for _ in range(50):
            await asyncio.sleep(0.05)
            if cloud.completed_commands:
                break
        runtime.request_stop()

    stop_task = asyncio.create_task(stop_after_full())
    await runtime.run()
    await stop_task

    # All cards re-sent in full resync
    assert len(cloud.synced_cards) >= 1
    assert len(cloud.synced_cards[0].cards) == 2

    # Command completed
    assert ("cmd-full", "completed", None) in cloud.completed_commands

    # Cursor did not roll back (it is at least "1")
    assert int(store.get_cursor("transactions") or 0) >= 1


# ---------------------------------------------------------------------------
# 4. Cycle failure completes with failed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cycle_failure_completes_with_failed(tmp_path: Path) -> None:
    """When a sync cycle fails during a command, complete is called with status='failed'."""
    db_file = tmp_path / "fail.db"
    store = StateStore(db_file)
    cloud = FakeCloudClient()

    source = FakeLoyaltySource()
    source.cards_error = SourceProtocolError("Simulated 1C query timeout")

    settings = AgentSettings(
        agent_env="test",
        agent_api_key="test-key-fail",
        agent_state_db_path=db_file,
    )

    runtime = AgentRuntime(
        settings=settings,
        state_store=store,
        cloud_client=cloud,
        source=source,
    )

    cmd = AgentCommandItem(id="cmd-err", type="sync_now")
    runtime._pending_commands.append(cmd)

    async def stop_after_fail() -> None:
        for _ in range(50):
            await asyncio.sleep(0.05)
            if cloud.completed_commands:
                break
        runtime.request_stop()

    stop_task = asyncio.create_task(stop_after_fail())
    await runtime.run()
    await stop_task

    assert len(cloud.completed_commands) == 1
    cmd_id, status, err = cloud.completed_commands[0]
    assert cmd_id == "cmd-err"
    assert status == "failed"
    assert err is not None
    assert "Simulated 1C query timeout" in err
    assert len(err) <= 512


# ---------------------------------------------------------------------------
# 5. Two commands execute sequentially
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_two_commands_execute_sequentially(tmp_path: Path) -> None:
    """Two queued commands execute in sequential order."""
    db_file = tmp_path / "two_cmds.db"
    store = StateStore(db_file)
    cloud = FakeCloudClient()
    source = FakeLoyaltySource()

    settings = AgentSettings(
        agent_env="test",
        agent_api_key="test-key-two-cmds",
        agent_state_db_path=db_file,
    )

    runtime = AgentRuntime(
        settings=settings,
        state_store=store,
        cloud_client=cloud,
        source=source,
    )

    cmd1 = AgentCommandItem(id="cmd-1", type="sync_now")
    cmd2 = AgentCommandItem(id="cmd-2", type="full_resync")
    runtime._pending_commands.extend([cmd1, cmd2])

    async def stop_after_both() -> None:
        for _ in range(50):
            await asyncio.sleep(0.05)
            if len(cloud.completed_commands) >= 2:
                break
        runtime.request_stop()

    stop_task = asyncio.create_task(stop_after_both())
    await runtime.run()
    await stop_task

    assert len(cloud.completed_commands) == 2
    assert cloud.completed_commands[0][0] == "cmd-1"
    assert cloud.completed_commands[0][1] == "completed"
    assert cloud.completed_commands[1][0] == "cmd-2"
    assert cloud.completed_commands[1][1] == "completed"


# ---------------------------------------------------------------------------
# 6. Retry complete on transient network error
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complete_retries_on_temporary_network_error(tmp_path: Path) -> None:
    """Transient network error when posting complete is retried without dropping command."""
    db_file = tmp_path / "complete_retry.db"
    store = StateStore(db_file)
    cloud = FakeCloudClient()
    source = FakeLoyaltySource()

    settings = AgentSettings(
        agent_env="test",
        agent_api_key="test-key-retry",
        agent_state_db_path=db_file,
    )

    runtime = AgentRuntime(
        settings=settings,
        state_store=store,
        cloud_client=cloud,
        source=source,
    )

    cloud.next_complete_error = CloudRetryableError("Connection reset by peer")

    cmd = AgentCommandItem(id="cmd-retry-1", type="sync_now")
    await runtime._complete_command_with_retry(cmd, status="completed", error=None)

    assert len(cloud.completed_commands) == 1
    assert cloud.completed_commands[0] == ("cmd-retry-1", "completed", None)


# ---------------------------------------------------------------------------
# 7. Cursor rollback defense unit tests
# ---------------------------------------------------------------------------

def test_cursor_ahead_or_equal_defense() -> None:
    """Unit test for is_cursor_ahead_or_equal logic."""
    assert is_cursor_ahead_or_equal("10", None) is True
    assert is_cursor_ahead_or_equal(None, "10") is False
    assert is_cursor_ahead_or_equal(None, None) is True
    assert is_cursor_ahead_or_equal("10", "10") is True

    assert is_cursor_ahead_or_equal("10", "5") is True
    assert is_cursor_ahead_or_equal("5", "10") is False

    t1 = encode_tx_done_cursor(
        TxDoneCursor(
            hw_period="2026-11-06T10:00:00+00:00",
            hw_doc_uuid="doc-1",
            hw_line=1,
            completed_at="2026-11-06T10:05:00+00:00",
        )
    )
    t2 = encode_tx_done_cursor(
        TxDoneCursor(
            hw_period="2026-11-06T12:00:00+00:00",
            hw_doc_uuid="doc-2",
            hw_line=1,
            completed_at="2026-11-06T12:05:00+00:00",
        )
    )

    assert is_cursor_ahead_or_equal(t2, t1) is True
    assert is_cursor_ahead_or_equal(t1, t2) is False
    assert is_cursor_ahead_or_equal(t1, t1) is True


# ---------------------------------------------------------------------------
# 8. OneComLoyaltySource full_resync bypasses known hashes
# ---------------------------------------------------------------------------

class MockRow:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)

    def __getattr__(self, name: str) -> Any:
        return self.__dict__.get(name, None)


class MockSelection:
    def __init__(self, rows: list[MockRow]) -> None:
        self.rows = rows
        self.idx = -1

    def Следующий(self) -> bool:
        self.idx += 1
        return self.idx < len(self.rows)

    def Next(self) -> bool:
        return self.Следующий()

    def __getattr__(self, name: str) -> Any:
        if 0 <= self.idx < len(self.rows):
            return getattr(self.rows[self.idx], name)
        raise AttributeError(name)


class MockQuery:
    def __init__(self, handler: Any) -> None:
        self.Текст = ""
        self.params: dict[str, Any] = {}
        self.handler = handler

    def УстановитьПараметр(self, name: str, val: Any) -> None:
        self.params[name] = val

    def SetParameter(self, name: str, val: Any) -> None:
        self.params[name] = val

    def Выполнить(self) -> Any:
        rows = self.handler(self.Текст, self.params)
        return type("MockQueryResult", (), {"Выбрать": lambda self_qr: MockSelection(rows)})()

    def Execute(self) -> Any:
        return self.Выполнить()


class MockComConnection:
    def __init__(self, query_handler: Any) -> None:
        self.handler = query_handler
        self.Метаданные = type("Meta", (), {
            "Имя": "POSCENTERONE",
            "Версия": "2.0.0.26.9",
        })()

    def NewObject(self, obj_type: str) -> Any:
        if obj_type in ("Запрос", "Query"):
            return MockQuery(self.handler)
        raise ValueError(f"Unknown object type: {obj_type}")

    def String(self, val: Any) -> str:
        return str(val)


@pytest.mark.asyncio
async def test_one_com_source_full_resync_bypasses_known_hashes(tmp_path: Path) -> None:
    """OneComLoyaltySource full_resync bypasses known card hashes and re-sends all cards."""
    db_file = tmp_path / "mock_one.db"
    store = StateStore(db_file)
    mapping_file = tmp_path / "mapping.json"
    from unittest.mock import MagicMock
    mapping_cfg = MagicMock(spec=OneMappingConfig)
    mapping_cfg.card_catalog_name = "Cards"
    mapping_cfg.card_id_field = "Ссылка"
    mapping_cfg.card_barcode_field = "Код"
    mapping_cfg.card_phone_field = "Телефон"
    mapping_cfg.card_full_name_field = "Наименование"
    mapping_cfg.balance_register_name = "CardBalances"
    mapping_cfg.balance_card_dimension = "Card"
    mapping_cfg.balance_resource = "Balance"
    mapping_cfg.balance_amount_resource = "СуммаОстаток"
    mapping_cfg.receipt_ref_enabled = False
    mapping_cfg.store_enabled = False

    settings = AgentSettings(
        agent_env="test",
        agent_api_key="test-key-mock-one",
        agent_state_db_path=db_file,
        one_mapping_path=mapping_file,
        one_adapter_mode="com",
        agent_one_initial_history_days=30,
    )

    card_uuid = "00000000-0000-0000-0000-000000000001"
    card_row = MockRow(
        Ссылка=card_uuid,
        Код="1000000000001",
        Телефон="+77011112233",
        Наименование="Test User",
        Баланс=100,
        Заблокирована=False,
        ПометкаУдаления=False,
    )

    def query_handler(sql: str, params: dict[str, Any]) -> list[MockRow]:
        if "Справочник." in sql or "Catalogs." in sql or "Cards" in sql:
            return [card_row]
        return []

    source = OneComLoyaltySource(settings, store, mapping_cfg)
    source._connection = MockComConnection(query_handler)

    # 1. Normal fetch: returns 1 card
    b1 = await source.fetch_cards(cursor=None, limit=10)
    assert len(b1.items) == 1

    # Commit pending cards into store (now known_hashes has this card!)
    cards_cur = decode_cards_cursor(b1.next_cursor)
    assert cards_cur is not None
    store.commit_pending_cards(cards_cur.session_id, None)
    assert card_uuid in store.get_card_hashes()

    # 2. Normal second fetch: hash is identical -> 0 cards
    b2 = await source.fetch_cards(cursor=None, limit=10)
    assert len(b2.items) == 0

    # 3. Request full resync
    source.prepare_full_resync()

    # 4. Fetch cards after full resync -> hash filter is bypassed, returns the card!
    b3 = await source.fetch_cards(cursor=None, limit=10)
    assert len(b3.items) == 1
    assert b3.items[0].barcode == "1000000000001"


# ---------------------------------------------------------------------------
# 9. OneComLoyaltySource multi-page full_resync paging and cursor defense
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_one_com_source_full_resync_multi_page_transactions(tmp_path: Path) -> None:
    """Multi-page full_resync on OneComLoyaltySource with Mock COM:
    - 3+ pages of transactions
    - Previous cursor is at the end of the window (TxDoneCursor)
    - Full resync sends all pages exactly once without repeating page 1
    - Final cursor is not behind previous cursor
    - Network break on page 2 preserves cursor not behind previous and subsequent normal sync works.
    """
    from datetime import timedelta
    from unittest.mock import MagicMock

    from poscenter_loyalty_agent.one_time import to_one_naive_datetime

    db_file = tmp_path / "mock_one_tx.db"
    store = StateStore(db_file)
    mapping_file = tmp_path / "mapping_tx.json"

    mapping_cfg = MagicMock(spec=OneMappingConfig)
    mapping_cfg.card_catalog_name = "Cards"
    mapping_cfg.card_id_field = "Ссылка"
    mapping_cfg.card_barcode_field = "Код"
    mapping_cfg.card_phone_field = "Телефон"
    mapping_cfg.card_full_name_field = "Наименование"
    mapping_cfg.balance_register_name = "CardBalances"
    mapping_cfg.balance_card_dimension = "БонуснаяКарта"
    mapping_cfg.balance_resource = "СуммаОстаток"
    mapping_cfg.balance_amount_resource = "СуммаОстаток"
    mapping_cfg.tx_register_name = "CardMovements"
    mapping_cfg.tx_occurred_at_field = "Период"
    mapping_cfg.tx_card_field = "БонуснаяКарта"
    mapping_cfg.tx_type_field = "ВидДвижения"
    mapping_cfg.tx_amount_field = "Сумма"
    mapping_cfg.tx_type_mapping = {"0": "accrual", "1": "redemption"}
    mapping_cfg.receipt_ref_enabled = False
    mapping_cfg.store_enabled = False
    mapping_cfg.verify_configuration = MagicMock(return_value=None)

    settings = AgentSettings(
        agent_env="test",
        agent_api_key="test-key-mock-tx",
        agent_state_db_path=db_file,
        one_mapping_path=mapping_file,
        one_adapter_mode="com",
        agent_one_initial_history_days=30,
        agent_tx_batch_size=2,  # 2 per page -> 5 tx = 3 pages!
        agent_card_batch_size=10,
    )

    now = datetime(2026, 11, 6, 12, 0, 0, tzinfo=UTC)
    card_uuid = "00000000-0000-0000-0000-000000000001"

    # 5 transaction rows with increasing timestamps
    movements_rows = []
    for i in range(1, 6):
        tx_time = now - timedelta(days=20) + timedelta(hours=i)
        movements_rows.append(
            MockRow(
                Период=to_one_naive_datetime(tx_time),
                Регистратор=f"00000000-0000-0000-0000-0000000000{i:02d}",
                НомерСтроки=1,
                БонуснаяКарта=card_uuid,
                КартаКод="1000000000001",
                ВидДвижения=0,  # 0 = Приход (accrual)
                Сумма=10 * i,
                ЧекНомер="",
                СкладНаименование="", 
            )
        )

    def query_handler(sql: str, params: dict[str, Any]) -> list[MockRow]:
        if "Справочник." in sql or "Cards" in sql:
            return []  # No cards
        if "Остатки(&WindowStart" in sql:
            return [MockRow(БонуснаяКарта=card_uuid, НачальныйОстаток=50)]
        if "РегистрНакопления." in sql:
            return movements_rows
        return []

    mock_conn = MockComConnection(query_handler)
    source = OneComLoyaltySource(settings, store, mapping_cfg, com_connector=mock_conn)

    # Establish previous cursor in StateStore at the end of the window
    prev_done_cursor = encode_tx_done_cursor(
        TxDoneCursor(
            hw_period=now.isoformat(),
            hw_doc_uuid="00000000-0000-0000-0000-000000000099",
            hw_line=1,
            completed_at=now.isoformat(),
        )
    )
    store.commit_cursor("transactions", prev_done_cursor, synced_at=now)
    assert store.get_cursor("transactions") == prev_done_cursor

    cloud = FakeCloudClient()
    runtime = AgentRuntime(settings=settings, state_store=store, cloud_client=cloud, source=source)

    # --- PART 1: Full resync runs cleanly across all 3 pages ---
    await runtime.sync_cycle(full_resync=True)

    # Check transactions received by cloud
    # 5 items total: page 1 (2), page 2 (2), page 3 (1) -> exactly 3 sync calls!
    assert len(cloud.synced_transactions) == 3, "Must be exactly 3 batches/pages"
    all_synced_ext_ids = [
        tx.external_id
        for payload in cloud.synced_transactions
        for tx in payload.transactions
    ]
    expected_ext_ids = [
        f"00000000-0000-0000-0000-0000000000{i:02d}:1" for i in range(1, 6)
    ]
    assert all_synced_ext_ids == expected_ext_ids, "All pages must be sent exactly once without repeating page 1!"
    assert len(all_synced_ext_ids) == 5

    # Cursor in store must NOT be behind prev_done_cursor
    cur_after = store.get_cursor("transactions")
    assert is_cursor_ahead_or_equal(cur_after, prev_done_cursor)

    # --- PART 2: Full resync breaks on page 2 ---
    call_count = 0
    orig_sync = cloud.sync_transactions

    async def fail_on_second_page(payload: Any) -> Any:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise CloudRetryableError("Network connection dropped on page 2")
        return await orig_sync(payload)

    cloud.sync_transactions = fail_on_second_page  # type: ignore[assignment]

    with pytest.raises(CloudRetryableError):
        await runtime.sync_cycle(full_resync=True)

    # State store cursor must STILL not be behind prev_done_cursor!
    cur_after_break = store.get_cursor("transactions")
    assert is_cursor_ahead_or_equal(cur_after_break, prev_done_cursor)

    # Source full_resync mode must be finished/reset
    assert getattr(source, "_full_resync_tx", False) is False

    # Next regular cycle works without error
    cloud.sync_transactions = orig_sync
    await runtime.sync_cycle(full_resync=False)

    await source.close()


# ---------------------------------------------------------------------------
# 10. Command failure preserves retry backoff delays
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_command_failure_preserves_retry_backoff_delays(tmp_path: Path) -> None:
    """When a remote command causes a cycle error, the trigger event is cleared
    so retry backoff pauses between attempts are strictly observed rather than skipped.
    """
    db_file = tmp_path / "backoff.db"
    store = StateStore(db_file)
    cloud = FakeCloudClient()
    source = FakeLoyaltySource()

    settings = AgentSettings(
        agent_env="test",
        agent_api_key="test-key-backoff",
        agent_state_db_path=db_file,
        agent_poll_interval_seconds=60,
        agent_sync_backoff_initial_seconds=1.0,
        agent_sync_backoff_max_seconds=30.0,
        agent_sync_backoff_jitter_ratio=0.0,
    )

    recorded_delays: list[float] = []

    async def mock_sleep(seconds: float) -> None:
        recorded_delays.append(seconds)
        # Yield control
        await asyncio.sleep(0.001)

    runtime = AgentRuntime(
        settings=settings,
        state_store=store,
        cloud_client=cloud,
        source=source,
        sleep_fn=mock_sleep,
    )

    # Simulate failing sync_cycle
    attempt_count = 0

    async def failing_sync_cycle(full_resync: bool = False) -> None:
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count >= 3:
            # Trigger shutdown after 3 failed attempts
            runtime._shutdown_event.set()
        raise CloudRetryableError("Cloud unavailable")

    runtime.sync_cycle = failing_sync_cycle  # type: ignore[assignment]

    # Enqueue a remote command
    runtime._pending_commands.append(AgentCommandItem(id="cmd-fail-1", type="sync_now"))
    runtime._sync_trigger_event.set()

    # Run sync loop
    await runtime._sync_loop()

    # Delays must have been recorded for each failure according to retry_state
    # Delay 1: 1.0 (after command failure)
    # Delay 2: 2.0 (after regular cycle attempt 2 failure)
    # Delay 3: 4.0 (after regular cycle attempt 3 failure)
    assert len(recorded_delays) >= 2, f"Delays were not honored! Recorded: {recorded_delays}"
    assert recorded_delays[0] == 1.0
    assert recorded_delays[1] == 2.0
    assert runtime.state_store.get_status().last_error is not None
