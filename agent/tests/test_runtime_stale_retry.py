"""Integration tests verifying guaranteed lifetime turnover delivery after ignored_stale.

Tests real AgentRuntime + real StateStore (persistent SQLite on disk, no wipe,
HMAC key preserved) + OneComLoyaltySource + simulated Cloud server.
Verifies mixed batches, single-card batches, and multi-page batches.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from poscenter_loyalty_agent.cloud_client import CloudClient
from poscenter_loyalty_agent.config import AgentSettings
from poscenter_loyalty_agent.models import (
    AgentCommandCompletePayload,
    AgentCommandsClaimResult,
    CardsSyncPayload,
    CardsSyncResult,
    HeartbeatPayload,
    HeartbeatResult,
    TransactionsSyncPayload,
    TransactionsSyncResult,
)
from poscenter_loyalty_agent.one_com_source import OneComLoyaltySource
from poscenter_loyalty_agent.runtime import AgentRuntime
from poscenter_loyalty_agent.state_store import StateStore, compute_card_hmac


class MockDateTimeWrapper:
    def __init__(self, current_dt: datetime) -> None:
        self.current_dt = current_dt

    def now(self, tz=None) -> datetime:
        return self.current_dt

    def fromisoformat(self, s: str) -> datetime:
        return datetime.fromisoformat(s)

    def __getattr__(self, name: str) -> Any:
        return getattr(datetime, name)


class SimulatedCloudServer(CloudClient):
    """Simulates Cloud backend's card ingestion and stale snapshot protection."""

    def __init__(self) -> None:
        self.cards: dict[str, dict[str, Any]] = {}
        self.sync_calls: list[CardsSyncPayload] = []

    def seed_card(
        self,
        barcode: str,
        updated_at: datetime,
        spend_total: Decimal | None = None,
        balance: Decimal = Decimal("0.0000"),
    ) -> None:
        self.cards[barcode] = {
            "barcode": barcode,
            "updated_at": updated_at,
            "spend_total": spend_total,
            "balance": balance,
        }

    async def sync_cards(self, payload: CardsSyncPayload) -> CardsSyncResult:
        self.sync_calls.append(payload)
        created = 0
        updated = 0
        ignored_stale = 0

        for item in payload.cards:
            if item.barcode in self.cards:
                existing = self.cards[item.barcode]
                # Stale protection: as_utc(incoming) <= as_utc(existing)
                if item.updated_at <= existing["updated_at"]:
                    ignored_stale += 1
                else:
                    existing["updated_at"] = item.updated_at
                    existing["balance"] = item.balance
                    if item.spend_total is not None:
                        existing["spend_total"] = item.spend_total
                    updated += 1
            else:
                self.cards[item.barcode] = {
                    "barcode": item.barcode,
                    "updated_at": item.updated_at,
                    "spend_total": item.spend_total,
                    "balance": item.balance,
                }
                created += 1

        return CardsSyncResult(
            received=len(payload.cards),
            created=created,
            updated=updated,
            ignored_stale=ignored_stale,
        )

    async def sync_transactions(self, payload: TransactionsSyncPayload) -> TransactionsSyncResult:
        return TransactionsSyncResult(
            received=len(payload.transactions),
            created=len(payload.transactions),
            duplicates=0,
        )

    async def send_heartbeat(self, payload: HeartbeatPayload) -> HeartbeatResult:
        return HeartbeatResult(status="ok")

    async def claim_commands(self) -> AgentCommandsClaimResult:
        return AgentCommandsClaimResult(commands=[])

    async def complete_command(self, command_id: str, payload: AgentCommandCompletePayload) -> None:
        pass

    async def close(self) -> None:
        pass


class Mock1CRow:
    def __init__(self, ref: str, code: str, balance: Any, turnover: Any) -> None:
        self.Ссылка = ref
        self.Код = code
        self.Телефон = "+77011112233"
        self.Наименование = "Тестовый Клиент"
        self.Заблокирована = False
        self.ПометкаУдаления = False
        self.Баланс = balance
        self.Оборот = turnover


class Mock1CSelection:
    def __init__(self, rows: list[Mock1CRow]) -> None:
        self.rows = rows
        self.idx = -1

    def Следующий(self) -> bool:
        self.idx += 1
        if self.idx < len(self.rows):
            for k, v in self.rows[self.idx].__dict__.items():
                setattr(self, k, v)
            return True
        return False

    def Next(self) -> bool:
        return self.Следующий()


def _create_mock_mapping():
    cfg = MagicMock()
    cfg.card_id_field = "Ссылка"
    cfg.card_barcode_field = "Код"
    cfg.card_phone_field = "Телефон"
    cfg.card_full_name_field = "Наименование"
    cfg.balance_amount_resource = "СуммаОстаток"
    cfg.card_catalog_name = "БонусныеКарты"
    cfg.balance_register_name = "ОстаткиБонусныхКарт"
    cfg.balance_card_dimension = "БонуснаяКарта"
    # Transactions mapping stubs so transactions stream doesn't crash
    cfg.tx_source_object = "ОстаткиБонусныхКарт"
    cfg.tx_period_field = "Период"
    cfg.tx_registrar_field = "Регистратор"
    cfg.tx_line_number_field = "НомерСтроки"
    cfg.tx_card_dim = "БонуснаяКарта"
    cfg.tx_type_field = "ВидДвижения"
    cfg.tx_amount_field = "Сумма"
    return cfg


@pytest.mark.asyncio
async def test_mixed_batch_stale_retry_with_real_runtime_and_state_store(tmp_path: Path):
    """Guaranteed lifetime turnover delivery after ignored_stale in a mixed batch.

    Scenario:
    - 1C contains:
        Card A ("200000000001", turnover=500000.0000)
        Card B ("200000000002", turnover=150000.0000)
    - Cloud server already has Card A updated at 12:00:00Z with spend_total=None.
    - Cloud server has Card B updated at 10:00:00Z with spend_total=None.
    - Cycle 1 runs with observation time 11:59:00Z (< 12:00:00Z).
        -> Cloud returns {received: 2, created: 0, updated: 1, ignored_stale: 1}.
        -> HTTP 200 does NOT mean all cards accepted: Card A turnover remains None.
        -> Real runtime and StateStore must NOT commit Card A to card_hashes.
        -> SQLite database is NOT wiped; HMAC keys are preserved.
    - Cycle 2 runs with observation time 12:01:00Z (> 12:00:00Z).
        -> 1C data did NOT change.
        -> Agent re-evaluates and re-delivers Card A with updated_at=12:01:00Z.
        -> Cloud accepts Card A (updated=1, ignored_stale=0).
        -> Card A turnover in Cloud is now 500000.0000!
        -> Card A is now committed to card_hashes.
    - Cycle 3 runs:
        -> 0 cards sent because HMACs match.
    """
    db_file = tmp_path / "persistent_agent_state.db"
    store = StateStore(db_file)
    cloud = SimulatedCloudServer()

    # Pre-seed Cloud server:
    t_server_card_a = datetime(2026, 11, 12, 12, 0, 0, tzinfo=UTC)
    t_server_card_b = datetime(2026, 11, 12, 10, 0, 0, tzinfo=UTC)
    cloud.seed_card("200000000001", updated_at=t_server_card_a, spend_total=None)
    cloud.seed_card("200000000002", updated_at=t_server_card_b, spend_total=None)

    # 1C source data (never changes throughout the test)
    one_c_rows = [
        Mock1CRow("ref-1", "200000000001", balance=100, turnover=500000),
        Mock1CRow("ref-2", "200000000002", balance=200, turnover=150000),
    ]

    settings = AgentSettings(
        agent_env="test",
        agent_key="test_agent_key_lifetime",
        cloud_base_url="https://cloud.example.com",
        agent_lifetime_turnover_enabled=True,
        agent_card_batch_size=10,  # Both cards sent together in a single batch
        one_adapter_mode="com",
    )

    mapping_cfg = _create_mock_mapping()
    source = OneComLoyaltySource(settings=settings, state_store=store, mapping_config=mapping_cfg)

    # Mock empty transactions to isolate cards stream
    async def mock_fetch_tx(cursor, limit):
        from poscenter_loyalty_agent.models import SourceBatch
        return SourceBatch(items=[], next_cursor=cursor, has_more=False)
    source.fetch_transactions = mock_fetch_tx

    runtime = AgentRuntime(
        settings=settings,
        state_store=store,
        cloud_client=cloud,
        source=source,
    )

    # --- CYCLE 1: Observation time is before server's Card A timestamp ---
    t_agent_cycle1 = datetime(2026, 11, 12, 11, 59, 0, tzinfo=UTC)

    with patch("poscenter_loyalty_agent.one_com_source.datetime", new=MockDateTimeWrapper(t_agent_cycle1)), \
         patch.object(source, "_get_connection"), \
         patch.object(source, "_execute_query", return_value=Mock1CSelection(one_c_rows)), \
         patch.object(source, "_get_ref_uuid", side_effect=lambda conn, ref: ref):

        await runtime.sync_cycle()

    # Verify Cycle 1 results:
    assert len(cloud.sync_calls) == 1
    cycle1_batch = cloud.sync_calls[0].cards
    assert len(cycle1_batch) == 2
    barcodes = [c.barcode for c in cycle1_batch]
    assert "200000000001" in barcodes
    assert "200000000002" in barcodes

    # Server state after Cycle 1:
    # Card B was accepted and its turnover updated
    assert cloud.cards["200000000002"]["spend_total"] == Decimal("150000.0000")
    # Card A was REJECTED as stale, spend_total remains None!
    assert cloud.cards["200000000001"]["spend_total"] is None

    # Agent SQLite state store verification:
    # Card A must NOT be committed to card_hashes because it was stale!
    persisted_hashes = store.get_card_hashes()
    assert "ref-1" not in persisted_hashes, "Stale Card A must NOT be committed to card_hashes!"

    # Verify SQLite file was NOT wiped/deleted
    assert db_file.exists()
    assert db_file.stat().st_size > 0

    # --- CYCLE 2: Real time passes so observation time is now AFTER server's timestamp ---
    t_agent_cycle2 = datetime(2026, 11, 12, 12, 1, 0, tzinfo=UTC)

    with patch("poscenter_loyalty_agent.one_com_source.datetime", new=MockDateTimeWrapper(t_agent_cycle2)), \
         patch.object(source, "_get_connection"), \
         patch.object(source, "_execute_query", return_value=Mock1CSelection(one_c_rows)), \
         patch.object(source, "_get_ref_uuid", side_effect=lambda conn, ref: ref):

        await runtime.sync_cycle()

    # Verify Cycle 2 results:
    assert len(cloud.sync_calls) == 2
    cycle2_batch = cloud.sync_calls[1].cards

    # Card A was re-evaluated and re-delivered
    card_a_items = [c for c in cycle2_batch if c.barcode == "200000000001"]
    assert len(card_a_items) == 1
    assert card_a_items[0].spend_total == Decimal("500000.0000")
    assert card_a_items[0].updated_at == t_agent_cycle2

    # Server state after Cycle 2:
    # Card A's turnover is now GUARANTEED delivered!
    assert cloud.cards["200000000001"]["spend_total"] == Decimal("500000.0000")
    assert cloud.cards["200000000002"]["spend_total"] == Decimal("150000.0000")

    # --- CYCLE 3: Idle cycle ---
    # Next cycle proves commit-on-next-fetch: CardsDoneCursor commits pending cards to card_hashes,
    # and with 1C unchanged, HMACs in SQLite match, so 0 cards are emitted.
    t_agent_cycle3 = datetime(2026, 11, 12, 12, 2, 0, tzinfo=UTC)

    with patch("poscenter_loyalty_agent.one_com_source.datetime", new=MockDateTimeWrapper(t_agent_cycle3)), \
         patch.object(source, "_get_connection"), \
         patch.object(source, "_execute_query", return_value=Mock1CSelection(one_c_rows)), \
         patch.object(source, "_get_ref_uuid", side_effect=lambda conn, ref: ref):

        await runtime.sync_cycle()

    # Agent SQLite state store now has Card A committed
    persisted_hashes_after_cycle3 = store.get_card_hashes()
    assert "ref-1" in persisted_hashes_after_cycle3
    assert "ref-2" in persisted_hashes_after_cycle3

    # No new sync calls made in Cycle 3
    assert len(cloud.sync_calls) == 2, "No cards should be sent when 1C has not changed!"


@pytest.mark.asyncio
async def test_single_card_stale_retry_with_real_runtime_and_state_store(tmp_path: Path):
    """Guaranteed turnover delivery for a single card rejected as stale."""
    db_file = tmp_path / "single_card_state.db"
    store = StateStore(db_file)
    cloud = SimulatedCloudServer()

    # Pre-seed Cloud server with newer timestamp
    t_server = datetime(2026, 11, 12, 15, 0, 0, tzinfo=UTC)
    cloud.seed_card("200000000099", updated_at=t_server, spend_total=None)

    one_c_rows = [Mock1CRow("ref-99", "200000000099", balance=50, turnover=750000)]

    settings = AgentSettings(
        agent_env="test",
        agent_key="test_agent_key_single",
        cloud_base_url="https://cloud.example.com",
        agent_lifetime_turnover_enabled=True,
        agent_card_batch_size=10,
        one_adapter_mode="com",
    )

    mapping_cfg = _create_mock_mapping()
    source = OneComLoyaltySource(settings=settings, state_store=store, mapping_config=mapping_cfg)

    async def mock_fetch_tx(cursor, limit):
        from poscenter_loyalty_agent.models import SourceBatch
        return SourceBatch(items=[], next_cursor=cursor, has_more=False)
    source.fetch_transactions = mock_fetch_tx

    runtime = AgentRuntime(
        settings=settings,
        state_store=store,
        cloud_client=cloud,
        source=source,
    )

    # Cycle 1: observation time is older than server's timestamp
    t1 = datetime(2026, 11, 12, 14, 59, 0, tzinfo=UTC)
    with patch("poscenter_loyalty_agent.one_com_source.datetime", new=MockDateTimeWrapper(t1)), \
         patch.object(source, "_get_connection"), \
         patch.object(source, "_execute_query", return_value=Mock1CSelection(one_c_rows)), \
         patch.object(source, "_get_ref_uuid", side_effect=lambda conn, ref: ref):

        await runtime.sync_cycle()

    assert cloud.cards["200000000099"]["spend_total"] is None
    assert "ref-99" not in store.get_card_hashes()

    # Cycle 2: observation time is newer than server's timestamp
    t2 = datetime(2026, 11, 12, 15, 1, 0, tzinfo=UTC)
    with patch("poscenter_loyalty_agent.one_com_source.datetime", new=MockDateTimeWrapper(t2)), \
         patch.object(source, "_get_connection"), \
         patch.object(source, "_execute_query", return_value=Mock1CSelection(one_c_rows)), \
         patch.object(source, "_get_ref_uuid", side_effect=lambda conn, ref: ref):

        await runtime.sync_cycle()

    assert cloud.cards["200000000099"]["spend_total"] == Decimal("750000.0000")

    # Cycle 3: unchanged, 0 calls; commits pending cards to card_hashes
    t3 = datetime(2026, 11, 12, 15, 2, 0, tzinfo=UTC)
    with patch("poscenter_loyalty_agent.one_com_source.datetime", new=MockDateTimeWrapper(t3)), \
         patch.object(source, "_get_connection"), \
         patch.object(source, "_execute_query", return_value=Mock1CSelection(one_c_rows)), \
         patch.object(source, "_get_ref_uuid", side_effect=lambda conn, ref: ref):

        await runtime.sync_cycle()

    assert "ref-99" in store.get_card_hashes()
    assert len(cloud.sync_calls) == 2


@pytest.mark.asyncio
async def test_multi_page_batch_partial_stale_retry(tmp_path: Path):
    """Multi-page pagination: Page 1 has stale card, Page 2 has clean card.

    Page 2 is committed. Page 1 is re-evaluated and delivered on next cycle.
    """
    db_file = tmp_path / "multi_page_state.db"
    store = StateStore(db_file)
    cloud = SimulatedCloudServer()

    # Pre-seed Cloud server:
    # Card 1 on Cloud is newer (12:00:00Z)
    cloud.seed_card("200000000001", updated_at=datetime(2026, 11, 12, 12, 0, 0, tzinfo=UTC), spend_total=None)
    # Card 2 on Cloud is older (10:00:00Z)
    cloud.seed_card("200000000002", updated_at=datetime(2026, 11, 12, 10, 0, 0, tzinfo=UTC), spend_total=None)

    one_c_rows = [
        Mock1CRow("ref-1", "200000000001", balance=10, turnover=111111),
        Mock1CRow("ref-2", "200000000002", balance=20, turnover=222222),
    ]

    settings = AgentSettings(
        agent_env="test",
        agent_key="test_agent_key_multipage",
        cloud_base_url="https://cloud.example.com",
        agent_lifetime_turnover_enabled=True,
        agent_card_batch_size=1,  # 1 card per page -> Page 1 = Card 1, Page 2 = Card 2
        one_adapter_mode="com",
    )

    mapping_cfg = _create_mock_mapping()
    source = OneComLoyaltySource(settings=settings, state_store=store, mapping_config=mapping_cfg)

    async def mock_fetch_tx(cursor, limit):
        from poscenter_loyalty_agent.models import SourceBatch
        return SourceBatch(items=[], next_cursor=cursor, has_more=False)
    source.fetch_transactions = mock_fetch_tx

    runtime = AgentRuntime(
        settings=settings,
        state_store=store,
        cloud_client=cloud,
        source=source,
    )

    # Cycle 1: observation time 11:59:00Z
    # Page 1 (Card 1) gets ignored_stale=1
    # Page 2 (Card 2) gets updated=1, ignored_stale=0
    t1 = datetime(2026, 11, 12, 11, 59, 0, tzinfo=UTC)
    with patch("poscenter_loyalty_agent.one_com_source.datetime", new=MockDateTimeWrapper(t1)), \
         patch.object(source, "_get_connection"), \
         patch.object(source, "_execute_query", return_value=Mock1CSelection(one_c_rows)), \
         patch.object(source, "_get_ref_uuid", side_effect=lambda conn, ref: ref):

        await runtime.sync_cycle()

    assert len(cloud.sync_calls) == 2
    assert cloud.cards["200000000002"]["spend_total"] == Decimal("222222.0000")
    assert cloud.cards["200000000001"]["spend_total"] is None

    # Card 1 must NOT be in card_hashes
    persisted = store.get_card_hashes()
    assert "ref-1" not in persisted

    # Cycle 2: observation time 12:01:00Z
    # Now only Card 1 should be re-sent, because Card 2 was already committed
    t2 = datetime(2026, 11, 12, 12, 1, 0, tzinfo=UTC)
    with patch("poscenter_loyalty_agent.one_com_source.datetime", new=MockDateTimeWrapper(t2)), \
         patch.object(source, "_get_connection"), \
         patch.object(source, "_execute_query", return_value=Mock1CSelection(one_c_rows)), \
         patch.object(source, "_get_ref_uuid", side_effect=lambda conn, ref: ref):

        await runtime.sync_cycle()

    # In Cycle 2, only Card 1 was sent (1 call)
    assert len(cloud.sync_calls) == 3
    cycle2_call = cloud.sync_calls[2].cards
    assert len(cycle2_call) == 1
    assert cycle2_call[0].barcode == "200000000001"
    assert cycle2_call[0].spend_total == Decimal("111111.0000")

    # Card 1 turnover is now delivered!
    assert cloud.cards["200000000001"]["spend_total"] == Decimal("111111.0000")

    # Cycle 3: idle; commits final page to card_hashes
    t3 = datetime(2026, 11, 12, 12, 2, 0, tzinfo=UTC)
    with patch("poscenter_loyalty_agent.one_com_source.datetime", new=MockDateTimeWrapper(t3)), \
         patch.object(source, "_get_connection"), \
         patch.object(source, "_execute_query", return_value=Mock1CSelection(one_c_rows)), \
         patch.object(source, "_get_ref_uuid", side_effect=lambda conn, ref: ref):

        await runtime.sync_cycle()

    assert "ref-1" in store.get_card_hashes()
    assert len(cloud.sync_calls) == 3


@pytest.mark.asyncio
async def test_existing_committed_hmac_stale_turnover_retry(tmp_path: Path):
    """Guaranteed redelivery of turnover change for already-synchronized card after ignored_stale.

    Demonstrates:
    - Card already has an existing committed HMAC in card_hashes (turnover 100000.0000).
    - In 1C, ONLY the turnover changes (to 250000.0000).
    - First push attempt is rejected by Cloud as stale (ignored_stale=1).
    - The existing committed hash is NOT wiped/deleted to force a fake success.
    - On next cycle with unchanged 1C source, after observation time advances,
      the changed turnover is re-sent and Cloud accepts it (updated=1, ignored_stale=0).
    - The following cycle sends 0 cards.
    """
    db_file = tmp_path / "committed_hmac_state.db"
    store = StateStore(db_file)
    cloud = SimulatedCloudServer()

    # Pre-seed existing card on Cloud:
    t_cloud_initial = datetime(2026, 11, 12, 12, 0, 0, tzinfo=UTC)
    cloud.seed_card("200000000077", updated_at=t_cloud_initial, spend_total=Decimal("100000.0000"))

    # Pre-seed existing committed HMAC in agent's StateStore:
    # Key used by agent:
    settings = AgentSettings(
        agent_env="test",
        agent_key="test_agent_key_existing_hmac",
        cloud_base_url="https://cloud.example.com",
        agent_lifetime_turnover_enabled=True,
        agent_card_batch_size=10,
        one_adapter_mode="com",
    )
    mapping_cfg = _create_mock_mapping()
    source = OneComLoyaltySource(settings=settings, state_store=store, mapping_config=mapping_cfg)

    async def mock_fetch_tx(cursor, limit):
        from poscenter_loyalty_agent.models import SourceBatch
        return SourceBatch(items=[], next_cursor=cursor, has_more=False)
    source.fetch_transactions = mock_fetch_tx

    old_dt = datetime(2026, 11, 12, 9, 0, 0, tzinfo=UTC)
    old_raw = "200000000077|+77011112233|Тестовый Клиент|False|100.0000|100000.0000"
    old_hmac = compute_card_hmac(source._hmac_key, old_raw)
    store.record_pending_cards(
        session_id="initial_session",
        page=1,
        cards=[("ref-77", old_hmac, old_dt.isoformat())],
    )
    store.commit_pending_cards("initial_session", 1)

    # Verify initial state in StateStore:
    initial_hashes = store.get_card_hashes()
    assert "ref-77" in initial_hashes
    assert initial_hashes["ref-77"][0] == old_hmac

    # 1C source data: ONLY turnover changed from 100000 to 250000!
    one_c_rows = [Mock1CRow("ref-77", "200000000077", balance=100, turnover=250000)]

    runtime = AgentRuntime(
        settings=settings,
        state_store=store,
        cloud_client=cloud,
        source=source,
    )

    # --- CYCLE 1: Agent observation clock is 11:59:00Z (before Cloud's 12:00:00Z) ---
    t1 = datetime(2026, 11, 12, 11, 59, 0, tzinfo=UTC)
    with patch("poscenter_loyalty_agent.one_com_source.datetime", new=MockDateTimeWrapper(t1)), \
         patch.object(source, "_get_connection"), \
         patch.object(source, "_execute_query", return_value=Mock1CSelection(one_c_rows)), \
         patch.object(source, "_get_ref_uuid", side_effect=lambda conn, ref: ref):

        await runtime.sync_cycle()

    # Cloud rejected the snapshot as stale:
    assert len(cloud.sync_calls) == 1
    assert cloud.cards["200000000077"]["spend_total"] == Decimal("100000.0000")  # untouched!

    # CRITICAL: Previous committed hash was NOT wiped/deleted to force artificial success!
    persisted_after_c1 = store.get_card_hashes()
    assert "ref-77" in persisted_after_c1
    assert persisted_after_c1["ref-77"][0] == old_hmac, "Old committed hash must still remain in SQLite!"

    # --- CYCLE 2: Observation clock advances to 12:01:00Z (> Cloud's 12:00:00Z) ---
    # 1C source data did NOT change.
    t2 = datetime(2026, 11, 12, 12, 1, 0, tzinfo=UTC)
    with patch("poscenter_loyalty_agent.one_com_source.datetime", new=MockDateTimeWrapper(t2)), \
         patch.object(source, "_get_connection"), \
         patch.object(source, "_execute_query", return_value=Mock1CSelection(one_c_rows)), \
         patch.object(source, "_get_ref_uuid", side_effect=lambda conn, ref: ref):

        await runtime.sync_cycle()

    # Cloud accepted the retry:
    assert len(cloud.sync_calls) == 2
    c2_cards = cloud.sync_calls[1].cards
    assert len(c2_cards) == 1
    assert c2_cards[0].barcode == "200000000077"
    assert c2_cards[0].spend_total == Decimal("250000.0000")
    assert c2_cards[0].updated_at == t2

    # Cloud turnover is now GUARANTEED updated to 250000!
    assert cloud.cards["200000000077"]["spend_total"] == Decimal("250000.0000")

    # --- CYCLE 3: Unchanged source, idle cycle ---
    t3 = datetime(2026, 11, 12, 12, 2, 0, tzinfo=UTC)
    with patch("poscenter_loyalty_agent.one_com_source.datetime", new=MockDateTimeWrapper(t3)), \
         patch.object(source, "_get_connection"), \
         patch.object(source, "_execute_query", return_value=Mock1CSelection(one_c_rows)), \
         patch.object(source, "_get_ref_uuid", side_effect=lambda conn, ref: ref):

        await runtime.sync_cycle()

    # New HMAC is now committed in StateStore:
    persisted_after_c3 = store.get_card_hashes()
    assert "ref-77" in persisted_after_c3
    new_raw = "200000000077|+77011112233|Тестовый Клиент|False|100.0000|250000.0000"
    new_hmac = compute_card_hmac(source._hmac_key, new_raw)
    assert persisted_after_c3["ref-77"][0] == new_hmac

    # 0 new sync calls in Cycle 3!
    assert len(cloud.sync_calls) == 2
