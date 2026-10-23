"""Characterization/regression tests for the 2026-10-23 mypy cleanup."""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from test_one_com_source import MockComConnection, MockRow

from poscenter_loyalty_agent import windows_service
from poscenter_loyalty_agent.config import AgentSettings
from poscenter_loyalty_agent.dry_run import DryRunCloudClient, run_sync_cycle
from poscenter_loyalty_agent.models import CardSyncItem, HeartbeatPayload, TransactionSyncItem
from poscenter_loyalty_agent.one_com_source import OneComLoyaltySource
from poscenter_loyalty_agent.one_mapping import OneMappingConfig
from poscenter_loyalty_agent.source import SourceProtocolError
from poscenter_loyalty_agent.stage0.data_profile import profile_recorder_types_detailed
from poscenter_loyalty_agent.state_store import StateStore


@pytest.mark.asyncio
async def test_dry_run_heartbeat_has_only_declared_status() -> None:
    client = DryRunCloudClient()
    result = await client.send_heartbeat(HeartbeatPayload(version="fixture"))
    assert result.model_dump() == {"status": "ok"}
    assert not hasattr(result, "next_check_in_seconds")
    assert client.heartbeat_count == 1
    print("HEARTBEAT_CONTRACT=status_only; no next_check_in_seconds at runtime")


@pytest.mark.asyncio
async def test_dry_run_keeps_card_and_transaction_batches_separate(
    agent_settings: AgentSettings, test_mapping: OneMappingConfig,
) -> None:
    now = datetime(2026, 10, 23, 12, tzinfo=UTC)
    cards = [MockRow(Ссылка=f"fixture-card-{i}", Код=f"00000000000{i}", Телефон="", Наименование="", Баланс=10) for i in (1, 2)]
    movements = [MockRow(Период=now, Регистратор=f"fixture-document-{i}", НомерСтроки=1, БонуснаяКарта=f"fixture-card-{i}", КартаКод=f"00000000000{i}", ВидДвижения="Приход", Сумма=10) for i in (1, 2)]

    def query_handler(query: str, params: dict[str, Any]) -> list[MockRow]:
        if "Справочник.БонусныеКарты" in query:
            return cards
        if "Остатки(&WindowStart" in query:
            return []
        return movements

    source = OneComLoyaltySource(agent_settings, StateStore(agent_settings.state_db_path), test_mapping, com_connector=MockComConnection(query_handler=query_handler))
    client = DryRunCloudClient()
    try:
        assert await run_sync_cycle(source, client, cards_limit=1, tx_limit=1) == (2, 2)
        assert all(isinstance(item, CardSyncItem) for item in client.received_cards)
        assert all(isinstance(item, TransactionSyncItem) for item in client.received_tx)
        assert [item.external_id for item in client.received_tx] == ["fixture-document-1:1", "fixture-document-2:1"]
        assert [item.balance_after for item in client.received_tx] == [Decimal("10.0000")] * 2
        assert client.cards_batch_count == client.tx_batch_count == 2
        print("DRY_RUN_BATCHES=2 cards + 2 transactions; types separate, pagination intact")
    finally:
        await source.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("period", [None, "synthetic-invalid-period", 123])
async def test_missing_transaction_period_characterization(
    agent_settings: AgentSettings, test_mapping: OneMappingConfig, period: object,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def query_handler(query: str, params: dict[str, Any]) -> list[MockRow]:
        return [MockRow(Период=period)]

    store = StateStore(agent_settings.state_db_path)
    source = OneComLoyaltySource(agent_settings, store, test_mapping, com_connector=MockComConnection(query_handler=query_handler))
    try:
        with pytest.raises(SourceProtocolError, match="1C transaction period must be a datetime"):
            await source.fetch_transactions(cursor=None, limit=10)
        assert store.get_cursor("transactions") is None
        assert store.get_known_tx_ids() == set()
        assert not any("ONE read completed" in record.getMessage() for record in caplog.records)
        print("INVALID_PERIOD_AFTER=SourceProtocolError; no cursor/ledger advancement or completion log")
    finally:
        await source.close()


def test_recorder_profile_error_keeps_existing_wire_shape() -> None:
    class BrokenConnection:
        def NewObject(self, name: str) -> Any:
            raise RuntimeError("synthetic query failure")

    result = profile_recorder_types_detailed(BrokenConnection())
    assert result == {"error": "Failed profiling recorders: synthetic query failure"}
    print("RECORDER_PROFILE_ERROR=string value in error dict; annotation was too narrow")


def test_frozen_service_attributes_preserved(monkeypatch: pytest.MonkeyPatch) -> None:
    # Load a fresh module without touching an installed Windows service or SCM.
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert windows_service.__file__ is not None
    spec = importlib.util.spec_from_file_location("tech_debt_service_fixture", Path(windows_service.__file__))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.POSCENTERLoyaltyAgentService._exe_name_ == sys.executable
    assert module.POSCENTERLoyaltyAgentService._exe_args_ == "service-run"
    print("FROZEN_SERVICE_ATTRIBUTES=existing executable + service-run; SCM not called")
