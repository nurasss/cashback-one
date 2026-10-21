"""Comprehensive test suite for OneComLoyaltySource with MockCom."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from poscenter_loyalty_agent.config import AgentSettings
from poscenter_loyalty_agent.one_com_source import (
    DECIMAL_4,
    OneComConnectionError,
    OneComLoyaltySource,
    OneComQueryError,
)
from poscenter_loyalty_agent.one_cursor import (
    TxDoneCursor,
    decode_cards_cursor,
    decode_tx_cursor,
    encode_tx_done_cursor,
)
from poscenter_loyalty_agent.one_mapping import (
    DOC_RETAIL_REPORT,
    FIELD_CARD_BLOCKED,
    FIELD_DELETION_MARK,
    FIELD_DOC_NUMBER,
    FIELD_LINE_NUMBER,
    FIELD_NAME,
    FIELD_REGISTRAR,
    FIELD_WAREHOUSE,
    OneMappingConfig,
)
from poscenter_loyalty_agent.one_time import to_one_naive_datetime
from poscenter_loyalty_agent.source import SourceError
from poscenter_loyalty_agent.stage0.mapping_models import calculate_mapping_fingerprint
from poscenter_loyalty_agent.state_store import StateStore, compute_card_hmac

# --- Mock COM Infrastructure ---


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
    def __init__(self, handler: Callable[[str, dict[str, Any]], list[MockRow]]) -> None:
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
    def __init__(
        self,
        conf_name: str = "POSCENTERONE",
        conf_version: str = "2.0.0.26.9",
        query_handler: Callable[[str, dict[str, Any]], list[MockRow]] | None = None,
    ) -> None:
        self.Metadata = type("Metadata", (), {"Name": conf_name, "Version": conf_version})()
        self.query_handler = query_handler or (lambda q, p: [])

    def NewObject(self, obj_type: str) -> Any:
        if obj_type == "Запрос":
            return MockQuery(self.query_handler)
        raise ValueError(f"Unknown 1C object type: {obj_type}")

    def String(self, val: Any) -> str:
        return str(val)

    def XMLСтрока(self, val: Any) -> str:
        return str(val)


# --- Test Fixtures ---


@pytest.fixture
def test_mapping(tmp_path: Path) -> OneMappingConfig:
    mapping_data = {
        "artifact_kind": "real_discovery",
        "mapping_version": "1.0.0",
        "one_configuration_identity": {
            "configuration_name": "POSCENTERONE",
            "configuration_version": "2.0.0.26.9",
            "platform_major": "8.3",
            "platform_version": "NOT_AVAILABLE",
            "platform_version_state": "NOT_STARTED",
        },
        "discovered_at": "2026-10-17T10:18:43Z",
        "cards": {
            "source_object": {"value": "Catalogs.БонусныеКарты", "state": "VERIFIED", "evidence": ["verified"]},
            "stable_source_id": {"value": "Ссылка", "state": "VERIFIED", "evidence": ["verified"]},
            "barcode_field": {"value": "Код", "state": "VERIFIED", "evidence": ["verified"]},
            "phone_field": {"value": "Телефон", "state": "VERIFIED", "evidence": ["verified"]},
            "full_name_field": {"value": "Наименование", "state": "VERIFIED", "evidence": ["verified"]},
            "balance_source": {
                "value": "AccumulationRegisters.ОстаткиБонусныхКарт.Остатки: измерение БонуснаяКарта, ресурс СуммаОстаток",
                "state": "VERIFIED",
                "evidence": ["verified"],
            },
            "blocked_source": {"value": "КартаЗапрещена ИЛИ ПометкаУдаления", "state": "VERIFIED", "evidence": ["verified"]},
            "updated_at_source": {"value": "ВерсияДанных", "state": "VERIFIED", "evidence": ["verified"]},
        },
        "transactions": {
            "source_object": {"value": "AccumulationRegisters.ОстаткиБонусныхКарт", "state": "VERIFIED", "evidence": ["verified"]},
            "stable_source_id": {"value": "Регистратор + НомерСтроки", "state": "VERIFIED", "evidence": ["verified"]},
            "card_relationship": {"value": "БонуснаяКарта", "state": "VERIFIED", "evidence": ["verified"]},
            "type_field": {"value": "ВидДвижения", "state": "VERIFIED", "evidence": ["verified"]},
            "type_mapping": {"value": {"Приход": "accrual", "Расход": "redemption"}, "state": "VERIFIED", "evidence": ["verified"]},
            "amount_field": {"value": "Сумма", "state": "VERIFIED", "evidence": ["verified"]},
            "occurred_at_field": {"value": "Период", "state": "VERIFIED", "evidence": ["verified"]},
            "balance_after_field": {"value": "derived", "state": "CANDIDATE", "evidence": ["candidate"]},
            "receipt_ref_field": {"value": "Регистратор.Номер", "state": "CANDIDATE", "evidence": ["candidate"]},
            "store_field": {"value": "Регистратор.Склад", "state": "CANDIDATE", "evidence": ["candidate"]},
        },
        "cursor_strategy": {
            "cards": {"value": {"strategy_name": "full_scan", "ordering_fields": ["Ссылка"], "tie_breaker": "Ссылка"}, "state": "VERIFIED", "evidence": ["verified"]},
            "transactions": {"value": {"strategy_name": "window", "ordering_fields": ["Период"], "tie_breaker": "НомерСтроки"}, "state": "VERIFIED", "evidence": ["verified"]},
        },
        "evidence": {
            "barcode_aggregate": {"sample_size": 10},
            "phone_aggregate": {"sample_size": 10},
            "name_aggregate": {"sample_size": 10},
            "balance_aggregate": {"sample_size": 10},
        },
        "mapping_sha256": "placeholder",
    }
    mapping_data["mapping_sha256"] = calculate_mapping_fingerprint(mapping_data)
    m_file = tmp_path / "mapping.json"
    m_file.write_text(json.dumps(mapping_data), encoding="utf-8")
    return OneMappingConfig.load(m_file, require_verified=True)


@pytest.fixture
def agent_settings(tmp_path: Path) -> AgentSettings:
    return AgentSettings(
        agent_api_key="test-api-key-123456",
        agent_env="development",
        one_adapter_mode="com",
        agent_state_db_path=tmp_path / "state.db",
        one_state_key_path=tmp_path / "agent.key",
        agent_one_lookback_days=3,
        agent_one_timezone="Asia/Almaty",
    )


# --- Tests ---


@pytest.mark.asyncio
async def test_cards_full_scan_pagination_and_ack_state_machine(
    agent_settings: AgentSettings, test_mapping: OneMappingConfig, tmp_path: Path
) -> None:
    """Test Scenarios 1-5: Full scan of 1200 cards, pagination by 500, ACK fixation, and retry idempotency."""
    store = StateStore(agent_settings.state_db_path)

    cards_data = [
        MockRow(
            Ссылка=f"card-uuid-{i:04d}",
            Код=f"100000{i:04d}",
            Телефон="+77011234567",
            Наименование=f"Customer {i}",
            КартаЗапрещена=False,
            ПометкаУдаления=False,
            Баланс=100 + i,
        )
        for i in range(1200)
    ]

    def query_handler(query_text: str, params: dict[str, Any]) -> list[MockRow]:
        if "Справочник.БонусныеКарты" in query_text:
            return cards_data
        return []

    mock_conn = MockComConnection(query_handler=query_handler)
    source = OneComLoyaltySource(agent_settings, store, test_mapping, com_connector=mock_conn)

    # Step 1: Initial fetch (limit = 500)
    batch1 = await source.fetch_cards(cursor=None, limit=500)
    assert len(batch1.items) == 500
    assert batch1.has_more is True
    assert batch1.next_cursor is not None
    assert batch1.items[0].barcode == "1000000000"
    # Fixation by ACK: card_hashes table is still untouched!
    assert len(store.get_card_hashes()) == 0

    # Step 2: Retry Scenario 3 (cloud error on page 1 -> runtime calls again with same cursor None)
    batch1_retry = await source.fetch_cards(cursor=None, limit=500)
    assert len(batch1_retry.items) == 500
    assert batch1_retry.items[0].barcode == batch1.items[0].barcode
    assert len(store.get_card_hashes()) == 0

    # Step 3: Page 1 ACKed (cloud returned 200 -> next call passes batch1_retry.next_cursor)
    batch2 = await source.fetch_cards(cursor=batch1_retry.next_cursor, limit=500)
    assert len(batch2.items) == 500
    assert batch2.has_more is True
    # Now page 1 (500 cards) has been committed to card_hashes!
    assert len(store.get_card_hashes()) == 500

    # Step 4: Page 2 ACKed
    batch3 = await source.fetch_cards(cursor=batch2.next_cursor, limit=500)
    assert len(batch3.items) == 200
    assert batch3.has_more is False  # Last page of 1200
    # Now page 2 has been committed -> 1000 in card_hashes
    assert len(store.get_card_hashes()) == 1000
    # Last page returns terminal done cursor!
    assert decode_cards_cursor(batch3.next_cursor) is not None

    # Step 5: Next cycle with terminal cursor (ACK of last page)
    batch_next = await source.fetch_cards(cursor=batch3.next_cursor, limit=500)
    # Remaining 200 committed -> total 1200!
    assert len(store.get_card_hashes()) == 1200
    # Since 1C data did not change, delta is empty!
    assert len(batch_next.items) == 0
    assert batch_next.has_more is False

    await source.close()


@pytest.mark.asyncio
async def test_cards_retry_after_cloud_failure_yields_exact_same_cards_and_order(
    agent_settings: AgentSettings, test_mapping: OneMappingConfig
) -> None:
    """Dedicated test: retry after cloud failure yields the exact same cards in the exact same order.

    Повтор после сбоя может иметь более позднее updated_at; для облака это безопасно
    (updated_at <= сохранённого игнорируется, новее — принимается).
    """
    store = StateStore(agent_settings.state_db_path)

    cards_data = [
        MockRow(
            Ссылка=f"uuid-{i:03d}",
            Код=f"777000{i:03d}",
            Телефон="+77011234567",
            Наименование=f"Customer {i}",
            КартаЗапрещена=False,
            ПометкаУдаления=False,
            Баланс=50 + i,
        )
        for i in range(15)
    ]

    mock_conn = MockComConnection(query_handler=lambda q, p: cards_data)
    source = OneComLoyaltySource(agent_settings, store, test_mapping, com_connector=mock_conn)

    # Initial attempt
    batch1 = await source.fetch_cards(cursor=None, limit=10)
    assert len(batch1.items) == 10

    # Retry after simulated cloud failure (cursor=None, as ACK was not received)
    batch1_retry = await source.fetch_cards(cursor=None, limit=10)
    assert len(batch1_retry.items) == 10

    # Ensure identical items in identical order
    for item_orig, item_retry in zip(batch1.items, batch1_retry.items, strict=True):
        assert item_orig.barcode == item_retry.barcode
        assert item_orig.phone == item_retry.phone
        assert item_orig.full_name == item_retry.full_name
        assert item_orig.balance == item_retry.balance
        assert item_orig.is_blocked == item_retry.is_blocked
        assert item_retry.updated_at >= item_orig.updated_at
        assert item_retry.updated_at.tzinfo == UTC

    await source.close()


@pytest.mark.asyncio
async def test_card_updated_at_unchanged_on_same_content_and_strictly_advances_on_mutation(
    agent_settings: AgentSettings, test_mapping: OneMappingConfig
) -> None:
    """Verify card is not resent if content hash unchanged, and updated_at strictly advances when mutated."""
    store = StateStore(agent_settings.state_db_path)

    card_record = MockRow(
        Ссылка="uuid-card-1",
        Код="777000111",
        Телефон="+77011234567",
        Наименование="Original Name",
        КартаЗапрещена=False,
        ПометкаУдаления=False,
        Баланс=100,
    )

    cards_data = [card_record]
    mock_conn = MockComConnection(query_handler=lambda q, p: cards_data)
    source = OneComLoyaltySource(agent_settings, store, test_mapping, com_connector=mock_conn)

    # Cycle 1: initial card discovery
    batch1 = await source.fetch_cards(cursor=None, limit=10)
    assert len(batch1.items) == 1
    t1 = batch1.items[0].updated_at
    assert t1.tzinfo == UTC

    # ACK commit of Cycle 1
    batch_ack = await source.fetch_cards(cursor=batch1.next_cursor, limit=10)
    # Stored in card_hashes
    assert "uuid-card-1" in store.get_card_hashes()
    # No changes on identical data
    assert len(batch_ack.items) == 0

    # Cycle 2: identical data in 1C -> not resent
    batch2 = await source.fetch_cards(cursor=batch1.next_cursor, limit=10)
    assert len(batch2.items) == 0

    # Cycle 3: balance changed in 1C (100 -> 150)
    card_record.Баланс = 150
    batch3 = await source.fetch_cards(cursor=batch1.next_cursor, limit=10)
    assert len(batch3.items) == 1
    t3 = batch3.items[0].updated_at
    assert t3 > t1
    assert t3.tzinfo == UTC
    assert batch3.items[0].balance == Decimal("150")

    # ACK commit of Cycle 3
    await source.fetch_cards(cursor=batch3.next_cursor, limit=10)

    # Cycle 4: name changed in 1C
    card_record.Наименование = "Mutated Name"
    batch4 = await source.fetch_cards(cursor=batch3.next_cursor, limit=10)
    assert len(batch4.items) == 1
    t4 = batch4.items[0].updated_at
    assert t4 > t3
    assert t4.tzinfo == UTC
    assert batch4.items[0].full_name == "Mutated Name"

    await source.close()


@pytest.mark.asyncio
async def test_cards_invalid_filtering_and_counters(
    agent_settings: AgentSettings, test_mapping: OneMappingConfig
) -> None:
    """Test filtering of non-digits, empty, too short, too long codes with counter tracking."""
    store = StateStore(agent_settings.state_db_path)

    cards_data = [
        MockRow(Ссылка="u-1", Код="", Телефон="", Наименование="", КартаЗапрещена=False, ПометкаУдаления=False, Баланс=0),
        MockRow(Ссылка="u-2", Код="ABC12345", Телефон="", Наименование="", КартаЗапрещена=False, ПометкаУдаления=False, Баланс=0),
        MockRow(Ссылка="u-3", Код="12345", Телефон="", Наименование="", КартаЗапрещена=False, ПометкаУдаления=False, Баланс=0),
        MockRow(Ссылка="u-4", Код="1234567890123456", Телефон="", Наименование="", КартаЗапрещена=False, ПометкаУдаления=False, Баланс=0),
        MockRow(Ссылка="u-5", Код="000123456", Телефон="+7 (701) 999-88-77", Наименование="Valid", КартаЗапрещена=False, ПометкаУдаления=True, Баланс=15),
    ]

    mock_conn = MockComConnection(query_handler=lambda q, p: cards_data)
    source = OneComLoyaltySource(agent_settings, store, test_mapping, com_connector=mock_conn)

    batch = await source.fetch_cards(cursor=None, limit=100)
    assert len(batch.items) == 1
    item = batch.items[0]
    assert item.barcode == "000123456"  # Leading zeroes preserved!
    assert item.phone == "+77019998877"  # Normalized
    assert item.is_blocked is True  # Marked for deletion

    # Counters check
    assert source.counters["cards_skipped_empty_code"] == 1
    assert source.counters["cards_skipped_non_digits"] == 1
    assert source.counters["cards_skipped_too_short"] == 1
    assert source.counters["cards_skipped_too_long"] == 1

    await source.close()


@pytest.mark.asyncio
async def test_transactions_window_p4_balance_after_and_ledger(
    agent_settings: AgentSettings, test_mapping: OneMappingConfig
) -> None:
    """Test Amendment П4: balance_after calculated over whole window, then already sent filtered."""
    store = StateStore(agent_settings.state_db_path)

    # Pre-populate tx_ledger with an already sent transaction: reg-1:1
    store.commit_pending_tx("t1_dummy_token")
    conn = store._get_connection()
    conn.execute(
        "INSERT INTO tx_ledger (external_id, period_utc, committed_at) VALUES (?, ?, ?)",
        ("reg-1:1", "2026-10-18T10:00:00Z", "2026-10-18T10:05:00Z"),
    )
    conn.commit()

    t0 = datetime(2026, 10, 18, 10, 0, 0, tzinfo=UTC)
    t1 = datetime(2026, 10, 18, 12, 0, 0, tzinfo=UTC)
    t2 = datetime(2026, 10, 18, 14, 0, 0, tzinfo=UTC)
    t3 = datetime(2026, 10, 18, 16, 0, 0, tzinfo=UTC)

    # 4 movements in window for Card A:
    # 1. reg-1:1 (already sent!) - accrual 100
    # 2. reg-2:1 (new)           - accrual 50
    # 3. reg-3:1 (new)           - redemption 20
    # 4. reg-4:1 (new)           - accrual 0 (skipped)
    movements_data = [
        MockRow(Период=t0, Регистратор="reg-1", НомерСтроки=1, БонуснаяКарта="card-A", КартаКод="777000111", ВидДвижения="Приход", Сумма=100, ЧекНомер="001", СкладНаименование="Store 1"),
        MockRow(Период=t1, Регистратор="reg-2", НомерСтроки=1, БонуснаяКарта="card-A", КартаКод="777000111", ВидДвижения="Приход", Сумма=50, ЧекНомер="002", СкладНаименование="Store 1"),
        MockRow(Период=t2, Регистратор="reg-3", НомерСтроки=1, БонуснаяКарта="card-A", КартаКод="777000111", ВидДвижения="Расход", Сумма=20, ЧекНомер="", СкладНаименование=""),
        MockRow(Период=t3, Регистратор="reg-4", НомерСтроки=1, БонуснаяКарта="card-A", КартаКод="777000111", ВидДвижения="Приход", Сумма=0, ЧекНомер="004", СкладНаименование="Store 2"),
    ]

    initial_balance_data = [
        MockRow(БонуснаяКарта="card-A", НачальныйОстаток=200),
    ]

    def query_handler(query_text: str, params: dict[str, Any]) -> list[MockRow]:
        if "Остатки(&WindowStart" in query_text:
            return initial_balance_data
        return movements_data

    mock_conn = MockComConnection(query_handler=query_handler)
    source = OneComLoyaltySource(agent_settings, store, test_mapping, com_connector=mock_conn)

    batch = await source.fetch_transactions(cursor=None, limit=100)

    # reg-1:1 was already sent -> filtered out!
    # reg-4:1 has sum 0 -> skipped!
    # Remaining: reg-2:1 and reg-3:1
    assert len(batch.items) == 2

    # Verification of balance_after (П4):
    # Initial: 200
    # After reg-1 (accrual 100): 300
    # After reg-2 (accrual 50): 350
    # After reg-3 (redemption 20): 330
    tx1 = batch.items[0]
    assert tx1.external_id == "reg-2:1"
    assert tx1.barcode == "777000111"
    assert tx1.type == "accrual"
    assert tx1.amount == Decimal("50")
    assert tx1.balance_after == Decimal("350")
    assert tx1.receipt_ref == "002"
    assert tx1.store == "Store 1"

    tx2 = batch.items[1]
    assert tx2.external_id == "reg-3:1"
    assert tx2.barcode == "777000111"
    assert tx2.type == "redemption"
    assert tx2.amount == Decimal("20")
    assert tx2.balance_after == Decimal("330")
    assert tx2.receipt_ref is None
    assert tx2.store is None

    # Next fetch confirms batch (ACK):
    decoded = decode_tx_cursor(batch.next_cursor)
    assert isinstance(decoded, TxDoneCursor)
    await source.fetch_transactions(cursor=batch.next_cursor, limit=100)

    # After ACK, reg-2:1 and reg-3:1 are committed to tx_ledger!
    known = store.get_known_tx_ids()
    assert "reg-2:1" in known
    assert "reg-3:1" in known
    assert "reg-1:1" in known

    await source.close()


@pytest.mark.asyncio
async def test_transactions_initial_balance_failure_raises_source_error(
    agent_settings: AgentSettings, test_mapping: OneMappingConfig
) -> None:
    """If initial balance at WindowStart cannot be fetched, raise SourceError without partial output."""
    store = StateStore(agent_settings.state_db_path)

    t0 = datetime(2026, 10, 18, 12, 0, 0, tzinfo=UTC)
    movements_data = [
        MockRow(Период=t0, Регистратор="reg-1", НомерСтроки=1, БонуснаяКарта="card-A", КартаКод="777000111", ВидДвижения="Приход", Сумма=50),
    ]

    def query_handler(query_text: str, params: dict[str, Any]) -> list[MockRow]:
        if "Остатки(&WindowStart" in query_text:
            raise RuntimeError("Database connection dropped during balance query")
        return movements_data

    mock_conn = MockComConnection(query_handler=query_handler)
    source = OneComLoyaltySource(agent_settings, store, test_mapping, com_connector=mock_conn)

    with pytest.raises(SourceError, match="Failed to fetch initial balances"):
        await source.fetch_transactions(cursor=None, limit=100)

    await source.close()


@pytest.mark.asyncio
async def test_zero_pii_in_cursors_and_storage(
    agent_settings: AgentSettings, test_mapping: OneMappingConfig
) -> None:
    """Verify that cursor tokens and SQLite tables contain ZERO PII."""
    store = StateStore(agent_settings.state_db_path)

    cards_data = [
        MockRow(
            Ссылка="card-secret-uuid-1",
            Код="777888999111",
            Телефон="+77011112233",
            Наименование="Иванов Иван Иванович",
            КартаЗапрещена=False,
            ПометкаУдаления=False,
            Баланс=500,
        )
    ]

    mock_conn = MockComConnection(query_handler=lambda q, p: cards_data)
    source = OneComLoyaltySource(agent_settings, store, test_mapping, com_connector=mock_conn)

    batch = await source.fetch_cards(cursor=None, limit=1)
    token = batch.next_cursor
    assert token is not None

    # 1. Cursor must not contain barcode, phone, or name
    decoded_card = decode_cards_cursor(token)
    assert decoded_card is not None
    token_str = str(token)
    assert "777888999111" not in token_str
    assert "+77011112233" not in token_str
    assert "Иванов" not in token_str

    # 2. ACK commit
    await source.fetch_cards(cursor=token, limit=1)

    # 3. SQLite card_hashes check: must not contain PII
    conn = store._get_connection()
    rows = conn.execute("SELECT * FROM card_hashes").fetchall()
    assert len(rows) == 1
    row_text = str(rows[0])
    assert "777888999111" not in row_text
    assert "+77011112233" not in row_text
    assert "Иванов" not in row_text

    await source.close()


@pytest.mark.parametrize(
    "keyword",
    [
        "ПОМЕСТИТЬ",
        "УДАЛИТЬ",
        "ЗАПИСАТЬ",
        "УСТАНОВИТЬ",
        "ИЗМЕНИТЬ",
        "СОЗДАТЬ",
        "DROP",
        "INSERT",
        "UPDATE",
        "DELETE",
    ],
)
def test_query_security_each_forbidden_keyword(keyword: str) -> None:
    """Verify that each forbidden keyword raises ValueError."""
    with pytest.raises(ValueError, match=f"Forbidden keyword '{keyword}'"):
        OneComLoyaltySource._validate_query_safety(f"ВЫБРАТЬ * ИЗ Справочник WHERE a = {keyword}")


def test_all_adapter_queries_pass_safety_validation(
    agent_settings: AgentSettings, test_mapping: OneMappingConfig
) -> None:
    """Verify that all queries constructed by OneComLoyaltySource pass the safety check."""
    store = StateStore(agent_settings.state_db_path)
    source = OneComLoyaltySource(agent_settings, store, test_mapping, com_connector=MockComConnection())

    cfg = test_mapping

    # 1. Cards query
    q_cards = f"""
ВЫБРАТЬ
    К.{cfg.card_id_field} КАК Ссылка,
    К.{cfg.card_barcode_field} КАК Код,
    К.{cfg.card_phone_field} КАК Телефон,
    К.{cfg.card_full_name_field} КАК Наименование,
    К.{FIELD_CARD_BLOCKED} КАК {FIELD_CARD_BLOCKED},
    К.{FIELD_DELETION_MARK} КАК {FIELD_DELETION_MARK},
    ЕСТЬNULL(Ост.{cfg.balance_amount_resource}, 0) КАК Баланс
ИЗ
    Справочник.{cfg.card_catalog_name} КАК К
    ЛЕВОЕ СОЕДИНЕНИЕ РегистрНакопления.{cfg.balance_register_name}.Остатки(, ) КАК Ост
        ПО К.{cfg.card_id_field} = Ост.{cfg.balance_card_dimension}
УПОРЯДОЧИТЬ ПО
    К.{cfg.card_id_field}
"""
    source._validate_query_safety(q_cards)

    # 2. Transactions query
    q_tx = f"""
ВЫБРАТЬ
    Т.{cfg.tx_occurred_at_field} КАК Период,
    Т.{FIELD_REGISTRAR} КАК {FIELD_REGISTRAR},
    Т.{FIELD_LINE_NUMBER} КАК {FIELD_LINE_NUMBER},
    Т.{cfg.tx_card_field} КАК БонуснаяКарта,
    Т.{cfg.tx_card_field}.{cfg.card_barcode_field} КАК КартаКод,
    Т.{cfg.tx_type_field} КАК ВидДвижения,
    Т.{cfg.tx_amount_field} КАК Сумма,
    ВЫБОР КОГДА Т.{FIELD_REGISTRAR} ССЫЛКА {DOC_RETAIL_REPORT} ТОГДА ВЫРАЗИТЬ(Т.{FIELD_REGISTRAR} КАК {DOC_RETAIL_REPORT}).{FIELD_DOC_NUMBER} ИНАЧЕ "" КОНЕЦ КАК ЧекНомер,
    ВЫБОР КОГДА Т.{FIELD_REGISTRAR} ССЫЛКА {DOC_RETAIL_REPORT} ТОГДА ВЫРАЗИТЬ(Т.{FIELD_REGISTRAR} КАК {DOC_RETAIL_REPORT}).{FIELD_WAREHOUSE}.{FIELD_NAME} ИНАЧЕ "" КОНЕЦ КАК СкладНаименование
ИЗ
    РегистрНакопления.{cfg.tx_register_name} КАК Т
ГДЕ
    Т.{cfg.tx_occurred_at_field} >= &WindowStart
УПОРЯДОЧИТЬ ПО
    Т.{cfg.tx_occurred_at_field},
    Т.{FIELD_REGISTRAR},
    Т.{FIELD_LINE_NUMBER}
"""
    source._validate_query_safety(q_tx)

    # 3. Initial balance query
    q_bal = f"""
ВЫБРАТЬ
    Т.{cfg.balance_card_dimension} КАК БонуснаяКарта,
    Т.{cfg.balance_amount_resource} КАК НачальныйОстаток
ИЗ
    РегистрНакопления.{cfg.balance_register_name}.Остатки(&WindowStart, ) КАК Т
"""
    source._validate_query_safety(q_bal)


def test_query_security_not_select() -> None:
    """Verify non-SELECT queries are blocked."""
    with pytest.raises(ValueError, match="Only queries starting with 'ВЫБРАТЬ' are allowed"):
        OneComLoyaltySource._validate_query_safety("UPDATE Table SET a = 1")


@pytest.mark.asyncio
async def test_com_error_recovery(agent_settings: AgentSettings, test_mapping: OneMappingConfig) -> None:
    """Verify com_error / query error resets connection cleanly without fatal crash."""
    store = StateStore(agent_settings.state_db_path)

    should_fail = True

    def query_handler(q: str, p: dict[str, Any]) -> list[MockRow]:
        nonlocal should_fail
        if should_fail:
            raise RuntimeError("Simulated COM 1C Infobase lock")
        return [
            MockRow(
                Ссылка="c-1",
                Код="111222333",
                Телефон="",
                Наименование="",
                КартаЗапрещена=False,
                ПометкаУдаления=False,
                Баланс=0,
            )
        ]

    mock_conn = MockComConnection(query_handler=query_handler)
    source = OneComLoyaltySource(agent_settings, store, test_mapping, com_connector=mock_conn)

    # First attempt fails with OneComQueryError
    with pytest.raises(OneComQueryError, match="Simulated COM 1C Infobase lock"):
        await source.fetch_cards(cursor=None, limit=10)

    # Connection was reset
    assert source._connection is None

    # Next attempt succeeds
    should_fail = False
    batch = await source.fetch_cards(cursor=None, limit=10)
    assert len(batch.items) == 1
    assert batch.items[0].barcode == "111222333"

    await source.close()


@pytest.mark.asyncio
async def test_sta_com_apartment_initialization_and_close(
    agent_settings: AgentSettings, test_mapping: OneMappingConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Item 1: pythoncom.CoInitialize called once across N calls, and CoUninitialize called once on close."""
    import sys
    import types

    init_calls = 0
    uninit_calls = 0

    def mock_co_init() -> None:
        nonlocal init_calls
        init_calls += 1

    def mock_co_uninit() -> None:
        nonlocal uninit_calls
        uninit_calls += 1

    mock_pythoncom = types.ModuleType("pythoncom")
    mock_pythoncom.CoInitialize = mock_co_init  # type: ignore[attr-defined]
    mock_pythoncom.CoUninitialize = mock_co_uninit  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pythoncom", mock_pythoncom)

    store = StateStore(agent_settings.state_db_path)
    mock_conn = MockComConnection(query_handler=lambda q, p: [])
    source = OneComLoyaltySource(agent_settings, store, test_mapping, com_connector=mock_conn)

    # Execute multiple calls across cards and transactions
    await source.fetch_cards(cursor=None, limit=10)
    await source.fetch_cards(cursor=None, limit=10)
    await source.fetch_transactions(cursor=None, limit=10)

    # CoInitialize must be called exactly once for the worker thread
    assert init_calls == 1
    assert uninit_calls == 0

    # Closing source triggers CoUninitialize in the same thread
    await source.close()
    assert uninit_calls == 1


@pytest.mark.asyncio
async def test_transactions_first_load_history_days(
    agent_settings: AgentSettings, test_mapping: OneMappingConfig
) -> None:
    """Item 2.3(a): First load (cursor=None) with initial history days (0 = 1990-01-01) finds old tx."""
    store = StateStore(agent_settings.state_db_path)
    agent_settings.agent_one_initial_history_days = 0

    t_old = datetime.now(UTC) - timedelta(days=10)
    captured_params: dict[str, Any] = {}

    def query_handler(q: str, p: dict[str, Any]) -> list[MockRow]:
        captured_params.update(p)
        if "Остатки(&WindowStart" in q:
            return [MockRow(БонуснаяКарта="c1", НачальныйОстаток=0)]
        return [
            MockRow(
                Период=t_old,
                Регистратор="reg-old",
                НомерСтроки=1,
                БонуснаяКарта="c1",
                КартаКод="123456789",
                ВидДвижения="Приход",
                Сумма=100,
            )
        ]

    mock_conn = MockComConnection(query_handler=query_handler)
    source = OneComLoyaltySource(agent_settings, store, test_mapping, com_connector=mock_conn)

    batch = await source.fetch_transactions(cursor=None, limit=10)
    assert len(batch.items) == 1
    assert batch.items[0].external_id == "reg-old:1"
    # Parameter WindowStart naive datetime must be from 1990
    assert captured_params["WindowStart"].year == 1990

    await source.close()


@pytest.mark.asyncio
async def test_transactions_restart_mid_pagination(
    agent_settings: AgentSettings, test_mapping: OneMappingConfig
) -> None:
    """Item 2.3(b): Restart mid-pagination takes window from cursor and doesn't duplicate or lose tx."""
    store = StateStore(agent_settings.state_db_path)

    t0 = datetime.now(UTC) - timedelta(hours=2)
    t1 = datetime.now(UTC) - timedelta(hours=1)
    movements_data = [
        MockRow(
            Период=t0,
            Регистратор="reg-1",
            НомерСтроки=1,
            БонуснаяКарта="c1",
            КартаКод="123456789",
            ВидДвижения="Приход",
            Сумма=50,
        ),
        MockRow(
            Период=t1,
            Регистратор="reg-2",
            НомерСтроки=1,
            БонуснаяКарта="c1",
            КартаКод="123456789",
            ВидДвижения="Приход",
            Сумма=70,
        ),
    ]

    def query_handler(q: str, p: dict[str, Any]) -> list[MockRow]:
        if "Остатки(&WindowStart" in q:
            return [MockRow(БонуснаяКарта="c1", НачальныйОстаток=10)]
        return movements_data

    mock_conn = MockComConnection(query_handler=query_handler)
    source = OneComLoyaltySource(agent_settings, store, test_mapping, com_connector=mock_conn)

    # 1. Fetch first page of 1 item
    batch1 = await source.fetch_transactions(cursor=None, limit=1)
    assert len(batch1.items) == 1
    assert batch1.items[0].external_id == "reg-1:1"
    assert batch1.has_more is True

    # 2. Simulate restart: clear in-memory active session
    source._active_tx_session = None

    # 3. Next fetch with cursor from batch1: incoming cursor confirms batch1 (commit_pending_tx),
    # then window is fetched using window_start/window_end from cursor, and reg-1:1 is filtered by ledger
    batch2 = await source.fetch_transactions(cursor=batch1.next_cursor, limit=1)
    assert len(batch2.items) == 1
    assert batch2.items[0].external_id == "reg-2:1"
    # Both items received across restart with zero duplication and zero loss
    assert batch1.items[0].external_id != batch2.items[0].external_id

    await source.close()


@pytest.mark.asyncio
async def test_transactions_max_window_rows_exceeded(
    agent_settings: AgentSettings, test_mapping: OneMappingConfig
) -> None:
    """Item 2.3(c): Exceeding AGENT_ONE_MAX_WINDOW_ROWS raises SourceError without leaking data."""
    store = StateStore(agent_settings.state_db_path)
    agent_settings.agent_one_max_window_rows = 2

    t0 = datetime.now(UTC)
    movements_data = [
        MockRow(
            Период=t0,
            Регистратор=f"reg-{i}",
            НомерСтроки=1,
            БонуснаяКарта="c1",
            КартаКод="123456789",
            ВидДвижения="Приход",
            Сумма=10,
        )
        for i in range(5)
    ]

    mock_conn = MockComConnection(query_handler=lambda q, p: movements_data)
    source = OneComLoyaltySource(agent_settings, store, test_mapping, com_connector=mock_conn)

    with pytest.raises(SourceError, match="Transaction window exceeded maximum allowed rows limit"):
        await source.fetch_transactions(cursor=None, limit=10)

    await source.close()


@pytest.mark.asyncio
async def test_transactions_empty_window_preserves_cursor(
    agent_settings: AgentSettings, test_mapping: OneMappingConfig
) -> None:
    """Item 2.3(d): Empty window returns empty batch and does not change cursor."""
    store = StateStore(agent_settings.state_db_path)
    mock_conn = MockComConnection(query_handler=lambda q, p: [])
    source = OneComLoyaltySource(agent_settings, store, test_mapping, com_connector=mock_conn)

    # Empty window with cursor=None
    batch_none = await source.fetch_transactions(cursor=None, limit=10)
    assert batch_none.items == []
    assert batch_none.next_cursor is None
    assert batch_none.has_more is False

    await source.close()


@pytest.mark.asyncio
async def test_transactions_unknown_type_skipped(
    agent_settings: AgentSettings, test_mapping: OneMappingConfig
) -> None:
    """Item 3: Unknown movement kind is skipped, logged, and does NOT affect balance_after."""
    store = StateStore(agent_settings.state_db_path)
    t0 = datetime.now(UTC) - timedelta(hours=1)
    t1 = datetime.now(UTC)

    # 1 unknown movement and 1 valid accrual
    movements_data = [
        MockRow(
            Период=t0,
            Регистратор="reg-unk",
            НомерСтроки=1,
            БонуснаяКарта="c1",
            КартаКод="123456789",
            ВидДвижения="НеизвестныйВид",
            Сумма=999,
        ),
        MockRow(
            Период=t1,
            Регистратор="reg-val",
            НомерСтроки=1,
            БонуснаяКарта="c1",
            КартаКод="123456789",
            ВидДвижения="Приход",
            Сумма=100,
        ),
    ]

    def query_handler(q: str, p: dict[str, Any]) -> list[MockRow]:
        if "Остатки(&WindowStart" in q:
            return [MockRow(БонуснаяКарта="c1", НачальныйОстаток=50)]
        return movements_data

    mock_conn = MockComConnection(query_handler=query_handler)
    source = OneComLoyaltySource(agent_settings, store, test_mapping, com_connector=mock_conn)

    batch = await source.fetch_transactions(cursor=None, limit=10)
    assert len(batch.items) == 1
    assert batch.items[0].external_id == "reg-val:1"
    # Initial balance 50 + 100 accrual = 150 (unknown movement with 999 did NOT participate!)
    assert batch.items[0].balance_after == Decimal("150")
    assert source.counters["tx_skipped_unknown_type"] == 1

    await source.close()


def test_queries_use_metadata_constants() -> None:
    """Item 5: Verify queries are constructed from standard 1C metadata constants."""
    assert FIELD_CARD_BLOCKED == "КартаЗапрещена"
    assert FIELD_DELETION_MARK == "ПометкаУдаления"
    assert FIELD_REGISTRAR == "Регистратор"
    assert FIELD_LINE_NUMBER == "НомерСтроки"
    assert DOC_RETAIL_REPORT == "Документ.ОтчетКассовойСмены"
    assert FIELD_DOC_NUMBER == "Номер"
    assert FIELD_WAREHOUSE == "Склад"
    assert FIELD_NAME == "Наименование"


@pytest.mark.asyncio
async def test_counters_separated_cards_and_tx(
    agent_settings: AgentSettings, test_mapping: OneMappingConfig
) -> None:
    """Item 6: Verify card counters and transaction counters are tracked separately."""
    store = StateStore(agent_settings.state_db_path)

    cards_data = [
        MockRow(
            Ссылка="u-1",
            Код="",
            Телефон="",
            Наименование="",
            КартаЗапрещена=False,
            ПометкаУдаления=False,
            Баланс=0,
        )
    ]
    tx_data = [
        MockRow(
            Период=datetime.now(UTC),
            Регистратор="r1",
            НомерСтроки=1,
            БонуснаяКарта="c1",
            КартаКод="",
            ВидДвижения="Приход",
            Сумма=10,
        )
    ]

    mock_conn = MockComConnection(query_handler=lambda q, p: cards_data if "Справочник" in q else tx_data)
    source = OneComLoyaltySource(agent_settings, store, test_mapping, com_connector=mock_conn)

    await source.fetch_cards(cursor=None, limit=10)
    assert source.counters["cards_skipped_empty_code"] == 1
    assert source.counters["tx_skipped_empty_code"] == 0

    await source.fetch_transactions(cursor=None, limit=10)
    assert source.counters["cards_skipped_empty_code"] == 1
    assert source.counters["tx_skipped_empty_code"] == 1

    await source.close()


def test_decimal_quantize_card_hash() -> None:
    """Item 7: Verify 50, 50.0, and '50.0000' produce the exact same card hash."""
    key = b"test_secret_key_32_bytes_long!!!"
    barcode = "123456789"
    phone = "+77011112233"
    name = "Test User"
    is_blocked = False

    hash_int = compute_card_hmac(
        key, f"{barcode}|{phone}|{name}|{is_blocked}|{Decimal(str(50)).quantize(DECIMAL_4)}"
    )
    hash_float = compute_card_hmac(
        key, f"{barcode}|{phone}|{name}|{is_blocked}|{Decimal(str(50.0)).quantize(DECIMAL_4)}"
    )
    hash_str = compute_card_hmac(
        key, f"{barcode}|{phone}|{name}|{is_blocked}|{Decimal('50.0000').quantize(DECIMAL_4)}"
    )

    assert hash_int == hash_float == hash_str


def test_one_com_connection_error_sanitization(
    agent_settings: AgentSettings, test_mapping: OneMappingConfig
) -> None:
    """Item 8: Verify passwords and usernames are redacted and masked in OneComConnectionError."""
    agent_settings.one_connection_string = 'Usr="super_admin";Pwd="super_secret_password_123";File="C:\\db"'
    store = StateStore(agent_settings.state_db_path)

    class FailingConnector:
        def Connect(self, cs: str) -> None:
            raise RuntimeError(
                'Connection failed with Usr="super_admin";Pwd="super_secret_password_123";File="C:\\db" at line 42'
            )

    source = OneComLoyaltySource(agent_settings, store, test_mapping, com_connector=FailingConnector())

    with pytest.raises(OneComConnectionError) as exc_info:
        source._get_connection()

    msg = str(exc_info.value)
    assert "super_secret_password_123" not in msg
    assert "super_admin" not in msg
    assert len(msg) <= 350


@pytest.mark.asyncio
async def test_transactions_service_downtime_10_days(
    agent_settings: AgentSettings, test_mapping: OneMappingConfig
) -> None:
    """Part 1.3(a): Service down for 10 days sends all movements occurred during downtime exactly once."""
    store = StateStore(agent_settings.state_db_path)
    now_utc = datetime.now(UTC)

    # 1. 10 days ago, service synced up to t_old_hw
    t_old_hw = now_utc - timedelta(days=10)
    old_done = TxDoneCursor(
        hw_period=t_old_hw.isoformat(),
        hw_doc_uuid="doc-old",
        hw_line=1,
        completed_at=t_old_hw.isoformat(),
    )
    old_cursor = encode_tx_done_cursor(old_done)

    # Store old doc in ledger
    store.record_pending_tx(old_cursor, [("doc-old:1", t_old_hw.isoformat())])
    store.commit_pending_tx(old_cursor)

    # Movements occurred during 10 days downtime
    t_mid1 = now_utc - timedelta(days=7)
    t_mid2 = now_utc - timedelta(days=3)
    t_now = now_utc - timedelta(hours=1)

    all_movements = [
        MockRow(Период=t_old_hw, Регистратор="doc-old", НомерСтроки=1, БонуснаяКарта="c1", КартаКод="123456789", ВидДвижения="Приход", Сумма=50),
        MockRow(Период=t_mid1, Регистратор="doc-downtime-1", НомерСтроки=1, БонуснаяКарта="c1", КартаКод="123456789", ВидДвижения="Приход", Сумма=60),
        MockRow(Период=t_mid2, Регистратор="doc-downtime-2", НомерСтроки=1, БонуснаяКарта="c1", КартаКод="123456789", ВидДвижения="Приход", Сумма=70),
        MockRow(Период=t_now, Регистратор="doc-downtime-3", НомерСтроки=1, БонуснаяКарта="c1", КартаКод="123456789", ВидДвижения="Приход", Сумма=80),
    ]

    def query_handler(q: str, p: dict[str, Any]) -> list[MockRow]:
        if "Остатки(&WindowStart" in q:
            return [MockRow(БонуснаяКарта="c1", НачальныйОстаток=100)]
        ws = p.get("WindowStart")
        if ws is not None:
            return [m for m in all_movements if to_one_naive_datetime(m.Период, "Asia/Almaty") >= ws]
        return all_movements

    mock_conn = MockComConnection(query_handler=query_handler)
    source = OneComLoyaltySource(agent_settings, store, test_mapping, com_connector=mock_conn)

    # Resume sync with old_cursor: window_start = t_old_hw - 3 days (13 days ago)
    batch = await source.fetch_transactions(cursor=old_cursor, limit=100)

    # doc-old:1 was already in ledger -> filtered out.
    # The 3 movements during downtime must all be returned!
    returned_ids = [tx.external_id for tx in batch.items]
    assert returned_ids == ["doc-downtime-1:1", "doc-downtime-2:1", "doc-downtime-3:1"]

    # Commit next cursor (ACK)
    assert batch.next_cursor is not None
    await source.fetch_transactions(cursor=batch.next_cursor, limit=100)

    # Subsequent cycle with latest cursor returns 0 items (nothing resent)
    next_batch = await source.fetch_transactions(cursor=batch.next_cursor, limit=100)
    assert len(next_batch.items) == 0

    await source.close()


@pytest.mark.asyncio
async def test_transactions_quiet_period_30_days(
    agent_settings: AgentSettings, test_mapping: OneMappingConfig
) -> None:
    """Part 1.3(b): 30 days quiet period does NOT resend old transactions on repeated cycles."""
    store = StateStore(agent_settings.state_db_path)
    now_utc = datetime.now(UTC)

    # Operation from 30 days ago
    t_30d = now_utc - timedelta(days=30)
    old_done = TxDoneCursor(
        hw_period=t_30d.isoformat(),
        hw_doc_uuid="doc-30d",
        hw_line=1,
        completed_at=t_30d.isoformat(),
    )
    old_cursor = encode_tx_done_cursor(old_done)

    # Recorded and committed in ledger 30 days ago
    store.record_pending_tx(old_cursor, [("doc-30d:1", t_30d.isoformat())])
    store.commit_pending_tx(old_cursor)

    # 1C still returns this movement in window [30d - 3d, now]
    movements_data = [
        MockRow(Период=t_30d, Регистратор="doc-30d", НомерСтроки=1, БонуснаяКарта="c1", КартаКод="123456789", ВидДвижения="Приход", Сумма=50)
    ]

    def query_handler(q: str, p: dict[str, Any]) -> list[MockRow]:
        if "Остатки(&WindowStart" in q:
            return [MockRow(БонуснаяКарта="c1", НачальныйОстаток=50)]
        return movements_data

    mock_conn = MockComConnection(query_handler=query_handler)
    source = OneComLoyaltySource(agent_settings, store, test_mapping, com_connector=mock_conn)

    # Sync cycle after 30 days: window_start is 33 days ago, ledger cutoff is 34 days ago -> doc-30d:1 NOT pruned
    batch = await source.fetch_transactions(cursor=old_cursor, limit=10)
    assert len(batch.items) == 0  # Filtered by ledger, NOT resent!

    await source.close()


@pytest.mark.asyncio
async def test_transactions_corrupted_cursor_fallback_to_initial_window(
    agent_settings: AgentSettings, test_mapping: OneMappingConfig
) -> None:
    """Part 1.3(c): Corrupted cursor falls back to initial window without exception."""
    store = StateStore(agent_settings.state_db_path)

    t0 = datetime.now(UTC) - timedelta(days=5)
    movements_data = [
        MockRow(Период=t0, Регистратор="doc-1", НомерСтроки=1, БонуснаяКарта="c1", КартаКод="123456789", ВидДвижения="Приход", Сумма=50)
    ]

    def query_handler(q: str, p: dict[str, Any]) -> list[MockRow]:
        if "Остатки(&WindowStart" in q:
            return [MockRow(БонуснаяКарта="c1", НачальныйОстаток=0)]
        return movements_data

    mock_conn = MockComConnection(query_handler=query_handler)
    source = OneComLoyaltySource(agent_settings, store, test_mapping, com_connector=mock_conn)

    # Pass corrupt token string
    batch = await source.fetch_transactions(cursor="corrupted_garbage_base64_string", limit=10)
    assert len(batch.items) == 1
    assert batch.items[0].external_id == "doc-1:1"

    await source.close()


@pytest.mark.asyncio
async def test_card_negative_balance_clamped_to_zero(
    agent_settings: AgentSettings, test_mapping: OneMappingConfig
) -> None:
    """Card with negative balance -45 is clamped to 0.0000 and cards_balance_clamped is incremented."""
    settings = agent_settings.model_copy(update={"agent_clamp_negative_balance": True})
    store = StateStore(settings.state_db_path)

    cards_data = [
        MockRow(
            Ссылка="uuid-neg-1",
            Код="777000111222",
            Телефон="+77011234567",
            Наименование="Negative Customer",
            КартаЗапрещена=False,
            ПометкаУдаления=False,
            Баланс=-45,
        )
    ]
    mock_conn = MockComConnection(query_handler=lambda q, p: cards_data)
    source = OneComLoyaltySource(settings, store, test_mapping, com_connector=mock_conn)

    batch = await source.fetch_cards(cursor=None, limit=10)
    assert len(batch.items) == 1
    assert batch.items[0].balance == Decimal("0.0000")
    assert source.counters["cards_balance_clamped"] == 1

    await source.close()


@pytest.mark.asyncio
async def test_tx_chain_running_balance_preserved_across_negative_clamping(
    agent_settings: AgentSettings, test_mapping: OneMappingConfig
) -> None:
    """Transaction chain with -20 then +50 gives balance_after 0 and 30, with tx_balance_after_clamped=1."""
    settings = agent_settings.model_copy(update={"agent_clamp_negative_balance": True})
    store = StateStore(settings.state_db_path)
    now_utc = datetime.now(UTC)

    t1 = now_utc - timedelta(hours=2)
    t2 = now_utc - timedelta(hours=1)

    movements = [
        MockRow(
            Период=t1,
            Регистратор="doc-redemption",
            НомерСтроки=1,
            БонуснаяКарта="uuid-card",
            КартаКод="777000111222",
            ВидДвижения="Расход",
            Сумма=20,
        ),
        MockRow(
            Период=t2,
            Регистратор="doc-accrual",
            НомерСтроки=1,
            БонуснаяКарта="uuid-card",
            КартаКод="777000111222",
            ВидДвижения="Приход",
            Сумма=50,
        ),
    ]

    def query_handler(q: str, p: dict[str, Any]) -> list[MockRow]:
        if "Остатки(&WindowStart" in q:
            return [MockRow(БонуснаяКарта="uuid-card", НачальныйОстаток=0)]
        return movements

    mock_conn = MockComConnection(query_handler=query_handler)
    source = OneComLoyaltySource(settings, store, test_mapping, com_connector=mock_conn)

    batch = await source.fetch_transactions(cursor=None, limit=10)
    assert len(batch.items) == 2
    # Movement 1: 0 - 20 = -20 -> clamped to 0
    assert batch.items[0].balance_after == Decimal("0.0000")
    # Movement 2: -20 + 50 = +30 -> true running balance accumulated, emitted as 30
    assert batch.items[1].balance_after == Decimal("30.0000")
    assert source.counters["tx_balance_after_clamped"] == 1

    await source.close()


@pytest.mark.asyncio
async def test_clamp_negative_balance_disabled_emits_negative(
    agent_settings: AgentSettings, test_mapping: OneMappingConfig
) -> None:
    """By default (agent_clamp_negative_balance=False), true negative balances are emitted for card and tx."""
    assert agent_settings.agent_clamp_negative_balance is False
    settings = agent_settings
    store = StateStore(settings.state_db_path)
    now_utc = datetime.now(UTC)

    cards_data = [
        MockRow(
            Ссылка="uuid-neg-1",
            Код="777000111222",
            Телефон="+77011234567",
            Наименование="Negative Customer",
            КартаЗапрещена=False,
            ПометкаУдаления=False,
            Баланс=-45,
        )
    ]
    t1 = now_utc - timedelta(hours=1)
    movements = [
        MockRow(
            Период=t1,
            Регистратор="doc-redemption",
            НомерСтроки=1,
            БонуснаяКарта="uuid-neg-1",
            КартаКод="777000111222",
            ВидДвижения="Расход",
            Сумма=20,
        )
    ]

    def query_handler(q: str, p: dict[str, Any]) -> list[MockRow]:
        if "Справочник" in q:
            return cards_data
        if "Остатки(&WindowStart" in q:
            return [MockRow(БонуснаяКарта="uuid-neg-1", НачальныйОстаток=0)]
        return movements

    mock_conn = MockComConnection(query_handler=query_handler)
    source = OneComLoyaltySource(settings, store, test_mapping, com_connector=mock_conn)

    # Card check
    c_batch = await source.fetch_cards(cursor=None, limit=10)
    assert len(c_batch.items) == 1
    assert c_batch.items[0].balance == Decimal("-45.0000")
    assert source.counters["cards_balance_clamped"] == 0

    # Tx check
    t_batch = await source.fetch_transactions(cursor=None, limit=10)
    assert len(t_batch.items) == 1
    assert t_batch.items[0].balance_after == Decimal("-20.0000")
    assert source.counters["tx_balance_after_clamped"] == 0

    await source.close()


@pytest.mark.asyncio
async def test_card_hash_stable_between_two_negative_balances(
    agent_settings: AgentSettings, test_mapping: OneMappingConfig
) -> None:
    """Card hash is stable when true balance changes between negative values (-45 -> -20): no extra emission."""
    settings = agent_settings.model_copy(update={"agent_clamp_negative_balance": True})
    store = StateStore(settings.state_db_path)

    current_balance = -45

    def query_handler(q: str, p: dict[str, Any]) -> list[MockRow]:
        return [
            MockRow(
                Ссылка="uuid-neg-1",
                Код="777000111222",
                Телефон="+77011234567",
                Наименование="Customer",
                КартаЗапрещена=False,
                ПометкаУдаления=False,
                Баланс=current_balance,
            )
        ]

    mock_conn = MockComConnection(query_handler=query_handler)
    source = OneComLoyaltySource(settings, store, test_mapping, com_connector=mock_conn)

    # Cycle 1: fetch card -> emitted with 0.0000
    batch1 = await source.fetch_cards(cursor=None, limit=10)
    assert len(batch1.items) == 1
    assert batch1.items[0].balance == Decimal("0.0000")

    # ACK / commit page 1
    done_cursor = batch1.next_cursor
    assert done_cursor is not None
    batch1_ack = await source.fetch_cards(cursor=done_cursor, limit=10)
    assert len(batch1_ack.items) == 0
    hashes = store.get_card_hashes()
    assert "uuid-neg-1" in hashes

    # Cycle 2: balance in 1C changes from -45 to -20 (both clamp to 0)
    current_balance = -20
    batch2 = await source.fetch_cards(cursor=done_cursor, limit=10)
    # Hash is stable: card not re-emitted!
    assert len(batch2.items) == 0

    # Cycle 3: balance in 1C becomes +15
    current_balance = 15
    batch3 = await source.fetch_cards(cursor=done_cursor, limit=10)
    # Value changed: card is emitted!
    assert len(batch3.items) == 1
    assert batch3.items[0].balance == Decimal("15.0000")

    await source.close()


# --- Diagnostic Logging Tests (Prompt 38) ---


@pytest.mark.asyncio
async def test_diagnostics_cards_read_zero_changes_logs_completion(
    agent_settings: AgentSettings, test_mapping: OneMappingConfig, caplog: pytest.LogCaptureFixture
) -> None:
    """Prompt 38: Verify INFO-level completion log for cards full scan with 0 changes."""
    store = StateStore(agent_settings.state_db_path)

    cards_data = [
        MockRow(
            Ссылка="card-uuid-0001",
            Код="1000000001",
            Телефон="+77011234567",
            Наименование="Customer 1",
            КартаЗапрещена=False,
            ПометкаУдаления=False,
            Баланс=150,
        ),
        MockRow(
            Ссылка="card-uuid-0002",
            Код="1000000002",
            Телефон="+77011234568",
            Наименование="Customer 2",
            КартаЗапрещена=False,
            ПометкаУдаления=False,
            Баланс=250,
        ),
    ]

    def query_handler(query_text: str, params: dict[str, Any]) -> list[MockRow]:
        if "Справочник.БонусныеКарты" in query_text:
            return cards_data
        return []

    mock_conn = MockComConnection(query_handler=query_handler)
    source = OneComLoyaltySource(agent_settings, store, test_mapping, com_connector=mock_conn)

    # Initial cycle commits all 2 cards into state store
    b1 = await source.fetch_cards(cursor=None, limit=10)
    assert len(b1.items) == 2
    # ACK cycle commits them to card_hashes
    assert b1.next_cursor is not None
    b1_ack = await source.fetch_cards(cursor=b1.next_cursor, limit=10)
    assert len(b1_ack.items) == 0

    # Steady-state cycle: 0 changes
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="poscenter_loyalty_agent.one_com_source"):
        batch = await source.fetch_cards(cursor=b1.next_cursor, limit=10)
        assert len(batch.items) == 0

    records = [
        r
        for r in caplog.records
        if r.name == "poscenter_loyalty_agent.one_com_source"
        and "ONE read completed: type=cards_snapshot" in r.message
    ]
    assert len(records) == 1
    rec = records[0]
    assert rec.levelno == logging.INFO
    pattern = r"^ONE read completed: type=cards_snapshot, records_read=2, changes_to_send=0, duration=\d+\.\d{3}s$"
    assert re.match(pattern, rec.message), f"Log message did not match expected format: {rec.message}"

    await source.close()


@pytest.mark.asyncio
async def test_diagnostics_transactions_read_with_changes_logs_completion(
    agent_settings: AgentSettings, test_mapping: OneMappingConfig, caplog: pytest.LogCaptureFixture
) -> None:
    """Prompt 38: Verify INFO-level completion log for transactions window with and without changes."""
    store = StateStore(agent_settings.state_db_path)
    now = datetime.now(UTC)

    # Pre-record one transaction as already known in store
    store.record_pending_tx("cursor-test", [("reg-uuid-0001:1", now.isoformat())])
    store.commit_pending_tx("cursor-test")

    tx_data = [
        # Already known (will be filtered out)
        MockRow(
            Период=now - timedelta(hours=2),
            Регистратор="reg-uuid-0001",
            НомерСтроки=1,
            БонуснаяКарта="card-uuid-0001",
            КартаКод="1000000001",
            ВидДвижения="Приход",
            Сумма=50,
            ЧекНомер="CHK-001",
            СкладНаименование="Store 1",
        ),
        # New transaction 1
        MockRow(
            Период=now - timedelta(hours=1),
            Регистратор="reg-uuid-0002",
            НомерСтроки=1,
            БонуснаяКарта="card-uuid-0001",
            КартаКод="1000000001",
            ВидДвижения="Приход",
            Сумма=100,
            ЧекНомер="CHK-002",
            СкладНаименование="Store 1",
        ),
        # New transaction 2
        MockRow(
            Период=now - timedelta(minutes=30),
            Регистратор="reg-uuid-0003",
            НомерСтроки=1,
            БонуснаяКарта="card-uuid-0002",
            КартаКод="1000000002",
            ВидДвижения="Расход",
            Сумма=30,
            ЧекНомер="CHK-003",
            СкладНаименование="Store 2",
        ),
    ]

    def query_handler(query_text: str, params: dict[str, Any]) -> list[MockRow]:
        if "РегистрНакопления.ОстаткиБонусныхКарт.Остатки" in query_text:
            return [
                MockRow(БонуснаяКарта="card-uuid-0001", НачальныйОстаток=500),
                MockRow(БонуснаяКарта="card-uuid-0002", НачальныйОстаток=200),
            ]
        if "РегистрНакопления.ОстаткиБонусныхКарт" in query_text:
            return tx_data
        return []

    mock_conn = MockComConnection(query_handler=query_handler)
    source = OneComLoyaltySource(agent_settings, store, test_mapping, com_connector=mock_conn)

    # 1. Fetch transactions with changes: 3 records read from 1C, 1 filtered as known, 2 changes to send
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="poscenter_loyalty_agent.one_com_source"):
        batch = await source.fetch_transactions(cursor=None, limit=10)
        assert len(batch.items) == 2

    records = [
        r
        for r in caplog.records
        if r.name == "poscenter_loyalty_agent.one_com_source"
        and "ONE read completed: type=transactions_window" in r.message
    ]
    assert len(records) == 1
    rec = records[0]
    assert rec.levelno == logging.INFO
    pattern = (
        r"^ONE read completed: type=transactions_window, records_read=3, changes_to_send=2, duration=\d+\.\d{3}s$"
    )
    assert re.match(pattern, rec.message), f"Log message did not match expected format: {rec.message}"

    # 2. Case with 0 raw movements (empty window)
    def empty_handler(query_text: str, params: dict[str, Any]) -> list[MockRow]:
        return []

    mock_conn_empty = MockComConnection(query_handler=empty_handler)
    source_empty = OneComLoyaltySource(agent_settings, store, test_mapping, com_connector=mock_conn_empty)

    caplog.clear()
    with caplog.at_level(logging.INFO, logger="poscenter_loyalty_agent.one_com_source"):
        batch_empty = await source_empty.fetch_transactions(cursor=None, limit=10)
        assert len(batch_empty.items) == 0

    empty_records = [
        r
        for r in caplog.records
        if r.name == "poscenter_loyalty_agent.one_com_source"
        and "ONE read completed: type=transactions_window" in r.message
    ]
    assert len(empty_records) == 1
    empty_rec = empty_records[0]
    empty_pattern = (
        r"^ONE read completed: type=transactions_window, records_read=0, changes_to_send=0, duration=\d+\.\d{3}s$"
    )
    assert re.match(empty_pattern, empty_rec.message), f"Log message did not match: {empty_rec.message}"

    await source.close()
    await source_empty.close()


@pytest.mark.asyncio
async def test_diagnostics_read_error_does_not_log_completion(
    agent_settings: AgentSettings, test_mapping: OneMappingConfig, caplog: pytest.LogCaptureFixture
) -> None:
    """Prompt 38: Verify that if 1C read fails (COM exception), success log is NOT emitted."""
    store = StateStore(agent_settings.state_db_path)

    def failing_handler(query_text: str, params: dict[str, Any]) -> list[MockRow]:
        raise RuntimeError("1C COM connection failed or timed out")

    mock_conn = MockComConnection(query_handler=failing_handler)
    source = OneComLoyaltySource(agent_settings, store, test_mapping, com_connector=mock_conn)

    # Cards query error
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="poscenter_loyalty_agent.one_com_source"):
        with pytest.raises(OneComQueryError):
            await source.fetch_cards(cursor=None, limit=10)

    cards_logs = [r for r in caplog.records if "ONE read completed" in r.message]
    assert len(cards_logs) == 0, f"Expected no completion log on error, got: {cards_logs}"

    # Transactions query error
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="poscenter_loyalty_agent.one_com_source"):
        with pytest.raises(OneComQueryError):
            await source.fetch_transactions(cursor=None, limit=10)

    tx_logs = [r for r in caplog.records if "ONE read completed" in r.message]
    assert len(tx_logs) == 0, f"Expected no completion log on error, got: {tx_logs}"

    await source.close()


@pytest.mark.asyncio
async def test_diagnostics_log_contains_no_pii_or_secrets(
    agent_settings: AgentSettings, test_mapping: OneMappingConfig, caplog: pytest.LogCaptureFixture
) -> None:
    """Prompt 38: Verify logs strictly do not contain PII (phones, names), barcodes, UUIDs, SQL queries, or secrets."""
    store = StateStore(agent_settings.state_db_path)
    now = datetime.now(UTC)

    sensitive_phone = "+77019998877"
    sensitive_name = "Иванов Иван Иванович"
    sensitive_barcode = "200000012345"
    sensitive_card_uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    sensitive_reg_uuid = "reg-uuid-secret-999"
    sensitive_receipt = "ЧЕК-998877"

    cards_data = [
        MockRow(
            Ссылка=sensitive_card_uuid,
            Код=sensitive_barcode,
            Телефон=sensitive_phone,
            Наименование=sensitive_name,
            КартаЗапрещена=False,
            ПометкаУдаления=False,
            Баланс=777,
        )
    ]

    tx_data = [
        MockRow(
            Период=now - timedelta(hours=1),
            Регистратор=sensitive_reg_uuid,
            НомерСтроки=1,
            БонуснаяКарта=sensitive_card_uuid,
            КартаКод=sensitive_barcode,
            ВидДвижения="Приход",
            Сумма=150,
            ЧекНомер=sensitive_receipt,
            СкладНаименование="Склад-Секретный",
        )
    ]

    def query_handler(query_text: str, params: dict[str, Any]) -> list[MockRow]:
        if "Справочник.БонусныеКарты" in query_text:
            return cards_data
        if "РегистрНакопления.ОстаткиБонусныхКарт.Остатки" in query_text:
            return [MockRow(БонуснаяКарта=sensitive_card_uuid, НачальныйОстаток=500)]
        if "РегистрНакопления.ОстаткиБонусныхКарт" in query_text:
            return tx_data
        return []

    mock_conn = MockComConnection(query_handler=query_handler)
    source = OneComLoyaltySource(agent_settings, store, test_mapping, com_connector=mock_conn)

    caplog.clear()
    with caplog.at_level(logging.INFO, logger="poscenter_loyalty_agent.one_com_source"):
        await source.fetch_cards(cursor=None, limit=10)
        await source.fetch_transactions(cursor=None, limit=10)

    diagnostic_records = [
        r.message
        for r in caplog.records
        if r.name == "poscenter_loyalty_agent.one_com_source" and "ONE read completed" in r.message
    ]
    assert len(diagnostic_records) == 2, f"Expected 2 diagnostic log lines, got: {diagnostic_records}"

    forbidden_substrings = [
        sensitive_phone,
        "9998877",
        sensitive_name,
        "Иванов",
        sensitive_barcode,
        sensitive_card_uuid,
        sensitive_reg_uuid,
        sensitive_receipt,
        "Склад-Секретный",
        "ВЫБРАТЬ",
        "SELECT",
        "WindowStart",
        "agent_api_key",
        "test-api-key",
    ]

    for msg in diagnostic_records:
        for forbidden in forbidden_substrings:
            assert forbidden not in msg, f"Forbidden substring '{forbidden}' found in diagnostic log: {msg}"

    await source.close()



