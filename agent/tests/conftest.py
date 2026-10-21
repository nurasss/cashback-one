"""Pytest configuration and global fixtures for poscenter-loyalty-agent."""
from __future__ import annotations

import os
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

# Isolate unit tests from live production ProgramData config (.env.service)
_test_pd = os.path.join(tempfile.gettempdir(), "cashback_test_pdata")
os.makedirs(_test_pd, exist_ok=True)
if os.environ.get("ProgramData") == r"C:\ProgramData":
    os.environ["ProgramData"] = _test_pd

from poscenter_loyalty_agent.config import AgentSettings, get_settings  # noqa: E402

if TYPE_CHECKING:
    from poscenter_loyalty_agent.one_mapping import OneMappingConfig


@pytest.fixture(autouse=True)
def isolate_one_connection_string(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Ensure sensitive or environment-specific variables are isolated from unit tests."""
    if hasattr(get_settings, "cache_clear"):
        get_settings.cache_clear()
    monkeypatch.delenv("ONE_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("AGENT_CLOUD_BASE_URL", raising=False)
    monkeypatch.delenv("AGENT_API_KEY", raising=False)
    try:
        yield
    finally:
        if hasattr(get_settings, "cache_clear"):
            get_settings.cache_clear()


@pytest.fixture
def test_mapping(tmp_path: Path) -> OneMappingConfig:
    import json

    from poscenter_loyalty_agent.one_mapping import OneMappingConfig
    from poscenter_loyalty_agent.stage0.mapping_models import calculate_mapping_fingerprint

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


sample_mapping_config = test_mapping


@pytest.fixture
def agent_settings(tmp_path: Path) -> AgentSettings:
    from poscenter_loyalty_agent.config import AgentSettings

    return AgentSettings(
        agent_api_key="test-api-key-123456",
        agent_env="development",
        one_adapter_mode="com",
        agent_state_db_path=tmp_path / "state.db",
        one_state_key_path=tmp_path / "agent.key",
        agent_one_lookback_days=3,
        agent_one_timezone="Asia/Almaty",
    )
