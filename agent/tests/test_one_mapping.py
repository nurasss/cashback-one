"""Tests for one_mapping module: loading, validation, and configuration identity checks."""

import json
from pathlib import Path

import pytest

from poscenter_loyalty_agent.one_mapping import (
    MappingValidationError,
    OneMappingConfig,
    load_one_mapping,
)


@pytest.fixture
def real_mapping_path() -> Path:
    p = Path(r"C:\cashback-stage0\stage0_mapping.json")
    if not p.exists():
        pytest.skip(f"Stage 0 mapping not found at {p}")
    return p


def test_load_real_stage0_mapping(real_mapping_path: Path) -> None:
    cfg = load_one_mapping(real_mapping_path, require_verified=True)

    assert cfg.expected_configuration_name == "POSCENTERONE"
    assert cfg.expected_configuration_version == "2.0.0.26.9"

    # Cards extraction
    assert cfg.card_catalog_name == "БонусныеКарты"
    assert cfg.card_barcode_field == "Код"
    assert cfg.card_phone_field == "Телефон"
    assert cfg.card_full_name_field == "Наименование"
    assert "ПометкаУдаления" in cfg.card_blocked_source

    # Balance extraction
    assert cfg.balance_register_name == "ОстаткиБонусныхКарт"
    assert cfg.balance_card_dimension == "БонуснаяКарта"
    assert cfg.balance_amount_resource == "СуммаОстаток"

    # Transactions extraction
    assert cfg.tx_register_name == "ОстаткиБонусныхКарт"
    assert cfg.tx_card_field == "БонуснаяКарта"
    assert cfg.tx_type_field == "ВидДвижения"
    assert cfg.tx_type_mapping == {"Приход": "accrual", "Расход": "redemption"}
    assert cfg.tx_amount_field == "Сумма"
    assert cfg.tx_occurred_at_field == "Период"

    # Candidate fields
    assert cfg.balance_after_enabled is True
    assert cfg.receipt_ref_enabled is True
    assert cfg.store_enabled is True


def test_verify_configuration_matching(real_mapping_path: Path) -> None:
    cfg = load_one_mapping(real_mapping_path, require_verified=True)

    # Exact match -> passes without warning
    warn = cfg.verify_configuration("POSCENTERONE", "2.0.0.26.9")
    assert warn is None


def test_verify_configuration_version_mismatch(real_mapping_path: Path) -> None:
    cfg = load_one_mapping(real_mapping_path, require_verified=True)

    # Different version -> warning returned, does not raise
    warn = cfg.verify_configuration("POSCENTERONE", "2.0.0.30.0")
    assert warn is not None
    assert "Configuration version mismatch" in warn
    assert "2.0.0.30.0" in warn


def test_verify_configuration_name_mismatch(real_mapping_path: Path) -> None:
    cfg = load_one_mapping(real_mapping_path, require_verified=True)

    # Different configuration name -> fatal MappingValidationError (MAPPING_INTEGRITY_ERROR)
    with pytest.raises(MappingValidationError, match="MAPPING_INTEGRITY_ERROR"):
        cfg.verify_configuration("Розница", "2.0.0.26.9")


def test_load_mapping_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(MappingValidationError, match="Mapping file not found"):
        OneMappingConfig.load(tmp_path / "nonexistent.json")


def test_load_mapping_invalid_json(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{invalid json", encoding="utf-8")
    with pytest.raises(MappingValidationError, match="Mapping validation failed"):
        OneMappingConfig.load(bad_file)


def test_load_mapping_unverified_rejected(real_mapping_path: Path, tmp_path: Path) -> None:
    # Read valid mapping and make one P0 field unverified
    data = json.loads(real_mapping_path.read_text(encoding="utf-8"))
    data["cards"]["barcode_field"]["state"] = "CANDIDATE"

    unverified_file = tmp_path / "unverified_mapping.json"
    unverified_file.write_text(json.dumps(data), encoding="utf-8")

    # With require_verified=True -> fails
    with pytest.raises(MappingValidationError, match="Mandatory mapping field 'cards.barcode_field' is not VERIFIED"):
        OneMappingConfig.load(unverified_file, require_verified=True)
