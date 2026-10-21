"""Tests for standalone dry-run runner and security inspection."""

from __future__ import annotations

import socket
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest

from poscenter_loyalty_agent.config import AgentSettings
from poscenter_loyalty_agent.dry_run import execute_dry_run
from poscenter_loyalty_agent.one_mapping import OneMappingConfig
from poscenter_loyalty_agent.stage0.sanitizer import contains_sensitive_data


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
    def __init__(
        self,
        conf_name: str = "POSCENTERONE",
        conf_version: str = "2.0.0.26.9",
        query_handler: Any = None,
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



@pytest.fixture
def mock_com_dryrun_data() -> MockComConnection:
    now_utc = datetime.now(UTC)
    t0 = now_utc - timedelta(hours=3)
    t1 = now_utc - timedelta(hours=2)
    t2 = now_utc - timedelta(hours=1)

    cards_data = [
        MockRow(
            Ссылка="c-1",
            Код="111222333444",
            Телефон="+77011112233",
            Наименование="Customer One",
            КартаЗапрещена=False,
            ПометкаУдаления=False,
            Баланс=150,
        ),
        MockRow(
            Ссылка="c-2",
            Код="555666777888",
            Телефон="",
            Наименование="Customer Two",
            КартаЗапрещена=False,
            ПометкаУдаления=False,
            Баланс=0,
        ),
        MockRow(
            Ссылка="c-invalid",
            Код="abc",
            Телефон="",
            Наименование="Invalid",
            КартаЗапрещена=False,
            ПометкаУдаления=False,
            Баланс=0,
        ),
    ]

    movements_data = [
        MockRow(
            Период=t0,
            Регистратор="doc-1",
            НомерСтроки=1,
            БонуснаяКарта="c-1",
            КартаКод="111222333444",
            ВидДвижения="Приход",
            Сумма=100,
            ЧекНомер="CHK-001",
            СкладНаименование="Store Central",
        ),
        MockRow(
            Период=t1,
            Регистратор="doc-2",
            НомерСтроки=1,
            БонуснаяКарта="c-1",
            КартаКод="111222333444",
            ВидДвижения="Приход",
            Сумма=50,
            ЧекНомер="",
            СкладНаименование="",
        ),
        MockRow(
            Период=t2,
            Регистратор="doc-3",
            НомерСтроки=1,
            БонуснаяКарта="c-1",
            КартаКод="111222333444",
            ВидДвижения="Приход",
            Сумма=0,  # Zero amount skip
            ЧекНомер="CHK-003",
            СкладНаименование="Store Central",
        ),
    ]

    initial_balance_data = [
        MockRow(БонуснаяКарта="c-1", НачальныйОстаток=0),
    ]

    def query_handler(q: str, p: dict[str, Any]) -> list[MockRow]:
        if "Справочник" in q:
            return cards_data
        if "Остатки(&WindowStart" in q:
            return initial_balance_data
        ws = p.get("WindowStart")
        if ws is not None:
            from poscenter_loyalty_agent.one_time import to_one_naive_datetime

            return [m for m in movements_data if to_one_naive_datetime(m.Период, "Asia/Almaty") >= ws]
        return movements_data

    return MockComConnection(query_handler=query_handler)


@pytest.mark.asyncio
async def test_dry_run_full_scenario_a_to_d(
    agent_settings: AgentSettings,
    test_mapping: OneMappingConfig,
    mock_com_dryrun_data: MockComConnection,
    tmp_path: Path,
) -> None:
    """Verify complete dry-run scenario A-D on MockCom with reconciliation and PII check."""
    dryrun_dir = tmp_path / "dryrun"
    report_file = tmp_path / "dryrun_report.md"

    res = await execute_dry_run(
        settings=agent_settings,
        mapping_config=test_mapping,
        com_connector=mock_com_dryrun_data,
        dryrun_dir=dryrun_dir,
        report_file_path=report_file,
    )

    # 1. Cycle 1
    assert res.cycle1_cards_sent == 2  # 2 valid cards (1 invalid skipped)
    assert res.cards_skipped_non_digits == 1
    assert res.cycle1_tx_sent == 2  # 2 positive movements (1 zero skipped)
    assert res.tx_skipped_zero_amount == 1

    # 2. Cycle 2 (immediate re-run)
    assert res.cycle2_cards_sent == 0
    assert res.cycle2_tx_sent == 0

    # 3. Cycle 3 (restart)
    assert res.cycle3_cards_sent == 0
    assert res.cycle3_tx_sent == 0

    # 4. Scenario D (failure recovery)
    assert res.scenario_d_cards_sent == res.cycle1_cards_sent
    assert res.scenario_d_tx_sent == res.cycle1_tx_sent

    # 5. Balance reconciliation: c-1 had initial 0 + 100 + 50 = 150; card balance is 150
    assert res.reconciliation_cards_checked == 1
    assert res.reconciliation_discrepancies == 0
    assert res.reconciliation_max_discrepancy == Decimal("0")

    # 6. Security & PII checks
    assert res.pii_db_check == "PASS"
    assert res.pii_key_check == "PASS"
    assert res.pii_log_check == "PASS"
    assert res.sanitizer_check == "PASS"

    # 7. Report file exists and contains zero PII
    assert report_file.exists()
    report_content = report_file.read_text(encoding="utf-8")
    assert not contains_sensitive_data(report_content)


@pytest.mark.asyncio
async def test_dry_run_network_isolation(
    agent_settings: AgentSettings,
    test_mapping: OneMappingConfig,
    mock_com_dryrun_data: MockComConnection,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify that DryRunCloudClient makes zero network/socket calls."""

    def forbidden_connect(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Network socket connect is strictly forbidden in dry-run mode!")

    def forbidden_httpx(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("HTTP client creation is strictly forbidden in dry-run mode!")

    monkeypatch.setattr(socket.socket, "connect", forbidden_connect)
    monkeypatch.setattr(httpx, "AsyncClient", forbidden_httpx)

    res = await execute_dry_run(
        settings=agent_settings,
        mapping_config=test_mapping,
        com_connector=mock_com_dryrun_data,
        dryrun_dir=tmp_path / "dryrun_net",
        report_file_path=tmp_path / "dryrun_net_report.md",
    )
    assert res.cycle1_cards_sent == 2
    assert res.cycle1_tx_sent == 2


@pytest.mark.asyncio
async def test_dry_run_pii_detection(
    agent_settings: AgentSettings,
    test_mapping: OneMappingConfig,
    mock_com_dryrun_data: MockComConnection,
    tmp_path: Path,
) -> None:
    """Verify that if raw PII somehow leaks into the SQLite database file, it is flagged as FAIL."""
    dryrun_dir = tmp_path / "dryrun_pii"
    dryrun_dir.mkdir(parents=True, exist_ok=True)
    db_path = dryrun_dir / "agent_state_dryrun.db"

    # Initialize valid StateStore schema first
    from poscenter_loyalty_agent.state_store import StateStore

    StateStore(db_path)

    # Pre-seed database with a leaked raw card barcode
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE leaked (val TEXT);")
    conn.execute("INSERT INTO leaked VALUES ('111222333444');")
    conn.commit()
    conn.close()

    res = await execute_dry_run(
        settings=agent_settings,
        mapping_config=test_mapping,
        com_connector=mock_com_dryrun_data,
        dryrun_dir=dryrun_dir,
        report_file_path=tmp_path / "dryrun_pii_report.md",
        clean_existing=False,
    )

    # Database check must catch the leak and report FAIL
    assert res.pii_db_check == "FAIL"


def test_tx_sort_key_integer_line_number() -> None:
    """Item 1.1: Verify external_id is sorted by integer line number, not string lexicography."""
    from poscenter_loyalty_agent.dry_run import _tx_sort_key
    from poscenter_loyalty_agent.models import TransactionSyncItem

    t_now = datetime.now(UTC)
    t1 = TransactionSyncItem(
        external_id="doc-uuid-1:2",
        barcode="111222333444",
        type="accrual",
        amount=Decimal("10"),
        balance_after=Decimal("10"),
        occurred_at=t_now,
    )
    t2 = TransactionSyncItem(
        external_id="doc-uuid-1:10",
        barcode="111222333444",
        type="accrual",
        amount=Decimal("20"),
        balance_after=Decimal("30"),
        occurred_at=t_now,
    )

    # String comparison is wrong ("doc-uuid-1:10" < "doc-uuid-1:2")
    assert t2.external_id < t1.external_id
    # Adapter sort key correctly places line 2 before line 10
    assert _tx_sort_key(t1) < _tx_sort_key(t2)


@pytest.mark.asyncio
async def test_dry_run_discrepancy_classification_same_period_ordering(
    agent_settings: AgentSettings,
    test_mapping: OneMappingConfig,
    tmp_path: Path,
) -> None:
    """Item 1.2(a): Discrepancy where any movement at max occurred_at equals card balance is classified as same_period_ordering."""
    now_utc = datetime.now(UTC)
    cards = [
        MockRow(
            Ссылка="c-1",
            Код="111222333444",
            Телефон="+77011112233",
            Наименование="Customer",
            КартаЗапрещена=False,
            ПометкаУдаления=False,
            Баланс=150,  # Card balance is 150
        )
    ]
    # Two movements at the exact same second:
    # Line 1: accrual 150 -> balance_after 150
    # Line 2: redemption 50 -> balance_after 100
    movements = [
        MockRow(
            Период=now_utc,
            Регистратор="doc-1",
            НомерСтроки=1,
            БонуснаяКарта="c-1",
            КартаКод="111222333444",
            ВидДвижения="Приход",
            Сумма=150,
            ЧекНомер="",
            СкладНаименование="",
        ),
        MockRow(
            Период=now_utc,
            Регистратор="doc-1",
            НомерСтроки=2,
            БонуснаяКарта="c-1",
            КартаКод="111222333444",
            ВидДвижения="Расход",
            Сумма=50,
            ЧекНомер="",
            СкладНаименование="",
        ),
    ]

    def query_handler(q: str, p: dict[str, Any]) -> list[MockRow]:
        if "Справочник" in q:
            return cards
        if "Остатки(&WindowStart" in q:
            return [MockRow(БонуснаяКарта="c-1", НачальныйОстаток=0)]
        return movements

    mock_com = MockComConnection(query_handler=query_handler)
    res = await execute_dry_run(
        settings=agent_settings,
        mapping_config=test_mapping,
        com_connector=mock_com,
        dryrun_dir=tmp_path / "dry_spo",
        report_file_path=tmp_path / "spo_report.md",
    )

    assert res.reconciliation_discrepancies == 1
    assert res.reconciliation_reasons.get("same_period_ordering") == 1


@pytest.mark.asyncio
async def test_dry_run_discrepancy_classification_skipped_movements(
    agent_settings: AgentSettings,
    test_mapping: OneMappingConfig,
    tmp_path: Path,
) -> None:
    """Item 1.2(b): Discrepancy where card has skipped zero-amount/unknown-type movements is classified as skipped_movements."""
    now_utc = datetime.now(UTC)
    cards = [
        MockRow(
            Ссылка="c-1",
            Код="111222333444",
            Телефон="+77011112233",
            Наименование="Customer",
            КартаЗапрещена=False,
            ПометкаУдаления=False,
            Баланс=150,  # Card balance is 150
        )
    ]
    # Movement 1: 100 accrual (balance_after = 100)
    # Movement 2: 0 accrual (skipped due to zero amount)
    movements = [
        MockRow(
            Период=now_utc - timedelta(minutes=5),
            Регистратор="doc-1",
            НомерСтроки=1,
            БонуснаяКарта="c-1",
            КартаКод="111222333444",
            ВидДвижения="Приход",
            Сумма=100,
            ЧекНомер="",
            СкладНаименование="",
        ),
        MockRow(
            Период=now_utc,
            Регистратор="doc-2",
            НомерСтроки=1,
            БонуснаяКарта="c-1",
            КартаКод="111222333444",
            ВидДвижения="Приход",
            Сумма=0,  # Skipped!
            ЧекНомер="",
            СкладНаименование="",
        ),
    ]

    def query_handler(q: str, p: dict[str, Any]) -> list[MockRow]:
        if "Справочник" in q:
            return cards
        if "Остатки(&WindowStart" in q:
            return [MockRow(БонуснаяКарта="c-1", НачальныйОстаток=0)]
        return movements

    mock_com = MockComConnection(query_handler=query_handler)
    res = await execute_dry_run(
        settings=agent_settings,
        mapping_config=test_mapping,
        com_connector=mock_com,
        dryrun_dir=tmp_path / "dry_sm",
        report_file_path=tmp_path / "sm_report.md",
    )

    assert res.reconciliation_discrepancies == 1
    assert res.reconciliation_reasons.get("skipped_movements") == 1


@pytest.mark.asyncio
async def test_dry_run_discrepancy_classification_other(
    agent_settings: AgentSettings,
    test_mapping: OneMappingConfig,
    tmp_path: Path,
) -> None:
    """Item 1.2(c): Discrepancy where neither same_period_ordering nor skipped_movements applies is classified as other."""
    now_utc = datetime.now(UTC)
    cards = [
        MockRow(
            Ссылка="c-1",
            Код="111222333444",
            Телефон="+77011112233",
            Наименование="Customer",
            КартаЗапрещена=False,
            ПометкаУдаления=False,
            Баланс=500,  # Card balance is 500
        )
    ]
    # Single movement: accrual 100 -> balance_after 100. Discrepancy = 400.
    movements = [
        MockRow(
            Период=now_utc,
            Регистратор="doc-1",
            НомерСтроки=1,
            БонуснаяКарта="c-1",
            КартаКод="111222333444",
            ВидДвижения="Приход",
            Сумма=100,
            ЧекНомер="",
            СкладНаименование="",
        ),
    ]

    def query_handler(q: str, p: dict[str, Any]) -> list[MockRow]:
        if "Справочник" in q:
            return cards
        if "Остатки(&WindowStart" in q:
            return [MockRow(БонуснаяКарта="c-1", НачальныйОстаток=0)]
        return movements

    mock_com = MockComConnection(query_handler=query_handler)
    res = await execute_dry_run(
        settings=agent_settings,
        mapping_config=test_mapping,
        com_connector=mock_com,
        dryrun_dir=tmp_path / "dry_other",
        report_file_path=tmp_path / "other_report.md",
    )

    assert res.reconciliation_discrepancies == 1
    assert res.reconciliation_reasons.get("other") == 1

