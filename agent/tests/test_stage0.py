"""Unit tests for Stage 0 Discovery Toolkit (TASK-009 Phase A).

Covers:
- Cross-platform CLI execution without tracebacks.
- Non-Windows environment returns NOT VERIFIED flags.
- Metadata inventory serialization and FakeMetadataProvider test seam.
- Mapping schema validation and placeholder detection.
- PII and credentials sanitizer (Requirement 33 security test).
- Deterministic mapping fingerprinting and tamper detection.
- Zero secrets in generated discovery artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from poscenter_loyalty_agent.main import cli
from poscenter_loyalty_agent.stage0 import (
    FLAG_NOT_VERIFIED,
    CandidateDiscoveryHeuristic,
    FakeMetadataProvider,
    MetadataField,
    MetadataObject,
    SecuritySanitizerError,
    calculate_mapping_fingerprint,
    check_environment,
    contains_sensitive_data,
    sanitize_text,
    scan_for_sensitive_data,
    validate_mapping,
    validate_safe_output,
)
from poscenter_loyalty_agent.stage0.report import (
    write_discovery_summary_report,
    write_environment_report,
    write_inventory_reports,
)


def test_non_windows_environment_reports_not_verified() -> None:
    """On non-Windows hosts, environment check safely reports NOT VERIFIED flags without errors."""
    result = check_environment()

    assert not result.is_windows
    assert not result.pywin32_available
    assert not result.com_connector_available
    assert not result.one_connection_successful
    assert not result.metadata_access_available

    flags = result.verification_flags
    assert flags.real_windows_service == FLAG_NOT_VERIFIED
    assert flags.real_v83_comconnector == FLAG_NOT_VERIFIED
    assert flags.real_one_connection == FLAG_NOT_VERIFIED
    assert flags.real_one_metadata_discovery == FLAG_NOT_VERIFIED
    assert flags.real_one_mapping == FLAG_NOT_VERIFIED

    console_text = result.format_console()
    assert "REAL_WINDOWS_SERVICE:        NOT VERIFIED" in console_text
    assert "REAL_V83_COMCONNECTOR:       NOT VERIFIED" in console_text
    assert "REAL_ONE_CONNECTION:         NOT VERIFIED" in console_text


def test_stage0_cli_cross_platform(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """CLI subcommands execute cleanly cross-platform."""
    out_dir = tmp_path / "stage0_out"

    # 1. stage0 check-environment
    cli(["stage0", "check-environment", "--output-dir", str(out_dir)])
    captured = capsys.readouterr()
    assert "Stage 0 Discovery Environment Check" in captured.out
    assert (out_dir / "environment.json").exists()

    # 2. stage0 validate-mapping on example mapping
    example_path = Path("agent/stage0_mapping.example.json")
    assert example_path.exists()
    cli(["stage0", "validate-mapping", str(example_path)])
    captured_val = capsys.readouterr()
    assert "Status:                 VALID" in captured_val.out

    # 3. stage0 probe-metadata on non-Windows host exits cleanly with code 1
    with pytest.raises(SystemExit) as exc_info:
        cli(["stage0", "probe-metadata", "--output-dir", str(out_dir)])
    assert exc_info.value.code == 1
    captured_probe = capsys.readouterr()
    assert "Real 1C COM metadata probing requires a Windows host" in captured_probe.err


def test_fake_metadata_provider_and_serialization(tmp_path: Path) -> None:
    """FakeMetadataProvider operates on synthetic neutral metadata and writes sanitized reports."""
    provider = FakeMetadataProvider()
    inventory = provider.discover_metadata()

    assert inventory.configuration.configuration_name == "TestConfigSynthetic"
    assert len(inventory.objects) == 2

    # Verify inventory reports serialization
    json_path, md_path = write_inventory_reports(inventory, tmp_path)
    assert json_path.exists()
    assert md_path.exists()

    # Read back JSON
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["configuration"]["configuration_name"] == "TestConfigSynthetic"
    assert len(data["objects"]) == 2

    # Read back Markdown
    md_content = md_path.read_text(encoding="utf-8")
    assert "# POSCENTER ONE Metadata Inventory" in md_content
    assert "ObjectA" in md_content
    assert "RegisterBonusA" in md_content


def test_pii_sanitizer_security_requirement_33() -> None:
    """Requirement 33: Reject or redact fake metadata containing PII and credentials."""
    dirty_text = (
        "Customer phone: +77001234567, Card Barcode: 0123456789012, "
        "User: Secret Person, Connection: Srvr=test;Ref=db;Pwd=secret;"
    )

    # 1. Detection
    findings = scan_for_sensitive_data(dirty_text)
    assert len(findings) >= 3  # Phone, Barcode, Pwd detected
    assert contains_sensitive_data(dirty_text)

    # 2. validate_safe_output raises SecuritySanitizerError
    with pytest.raises(SecuritySanitizerError) as exc_info:
        validate_safe_output(dirty_text, context="TestArtifact")
    assert "Security safety violation" in str(exc_info.value)

    # 3. Sanitization
    cleaned = sanitize_text(dirty_text)
    assert "+77001234567" not in cleaned
    assert "0123456789012" not in cleaned
    assert "Pwd=secret" not in cleaned
    assert "[PHONE_REDACTED]" in cleaned
    assert "[BARCODE_REDACTED]" in cleaned
    assert "Pwd=***REDACTED***" in cleaned


def test_mapping_schema_validation(tmp_path: Path) -> None:
    """Mapping validator enforces complete schema and detects missing required elements."""
    example_path = Path("agent/stage0_mapping.example.json")
    valid_data = json.loads(example_path.read_text(encoding="utf-8"))

    # Missing cards.barcode_field
    invalid_data = json.loads(json.dumps(valid_data))
    del invalid_data["cards"]["barcode_field"]
    invalid_data["mapping_sha256"] = calculate_mapping_fingerprint(invalid_data)

    test_file = tmp_path / "invalid_mapping.json"
    test_file.write_text(json.dumps(invalid_data), encoding="utf-8")

    report = validate_mapping(test_file)
    assert not report.is_valid
    assert any("cards.barcode_field" in err for err in report.errors)


def test_placeholder_detection(tmp_path: Path) -> None:
    """Mapping containing placeholders like TODO, guess, or unknown_object is rejected."""
    example_path = Path("agent/stage0_mapping.example.json")
    data = json.loads(example_path.read_text(encoding="utf-8"))

    # Inject forbidden placeholder
    data["cards"]["barcode_field"] = "TODO_find_barcode_field"
    data["mapping_sha256"] = calculate_mapping_fingerprint(data)

    test_file = tmp_path / "placeholder_mapping.json"
    test_file.write_text(json.dumps(data), encoding="utf-8")

    report = validate_mapping(test_file)
    assert not report.is_valid
    assert any("Placeholder 'TODO' detected" in err for err in report.errors)


def test_mapping_fingerprint_stability_and_tamper_detection(tmp_path: Path) -> None:
    """Fingerprint is deterministic and changes immediately if mapping is tampered with."""
    example_path = Path("agent/stage0_mapping.example.json")
    data = json.loads(example_path.read_text(encoding="utf-8"))

    original_fp = calculate_mapping_fingerprint(data)
    repeat_fp = calculate_mapping_fingerprint(data)
    assert original_fp == repeat_fp

    # Tamper with single field without updating fingerprint
    tampered_data = json.loads(json.dumps(data))
    tampered_data["cards"]["barcode_field"] = "AlteredBarcodeField"
    # Keep original declared fingerprint
    tampered_data["mapping_sha256"] = original_fp

    test_file = tmp_path / "tampered_mapping.json"
    test_file.write_text(json.dumps(tampered_data), encoding="utf-8")

    report = validate_mapping(test_file)
    assert not report.is_valid
    assert any("Fingerprint mismatch" in err for err in report.errors)


def test_zero_secrets_in_generated_discovery_report(tmp_path: Path) -> None:
    """Generated environment and summary reports contain zero secrets or credentials."""
    env_result = check_environment()
    provider = FakeMetadataProvider()
    inventory = provider.discover_metadata()

    env_path = write_environment_report(env_result, tmp_path)
    summary_path = write_discovery_summary_report(env_result, inventory, tmp_path)

    env_text = env_path.read_text(encoding="utf-8")
    summary_text = summary_path.read_text(encoding="utf-8")

    # Confirm neither artifact contains secrets or PII
    assert not contains_sensitive_data(env_text)
    assert not contains_sensitive_data(summary_text)
    assert "one_connection_string" not in env_text.lower()
    assert "password" not in env_text.lower()
    assert "pwd=" not in summary_text.lower()


def test_candidate_discovery_heuristics() -> None:
    """Heuristic identification flags candidate cards and registers with manual verification required."""
    sample_objects = [
        MetadataObject(
            category="Catalogs",
            name="LoyaltyCardsCatalog",
            synonym="Карты Лояльности",
            fields=[
                MetadataField(name="BarcodeNumber", synonym="Штрихкод", type_desc="String(13)"),
                MetadataField(name="CustomerPhone", synonym="Телефон", type_desc="String(20)"),
            ],
        ),
        MetadataObject(
            category="AccumulationRegisters",
            name="BonusPointsRegister",
            synonym="Остатки Бонусов",
            fields=[
                MetadataField(name="Card", synonym="Карта", type_desc="CatalogRef", is_dimension=True),
                MetadataField(name="BonusBalance", synonym="Остаток", type_desc="Number(15,2)", is_resource=True),
            ],
        ),
        MetadataObject(
            category="Catalogs",
            name="UnrelatedNomenclature",
            synonym="Товары и услуги",
            fields=[MetadataField(name="Articul", type_desc="String(50)")],
        ),
    ]

    cards, txs, regs = CandidateDiscoveryHeuristic.analyze(sample_objects)

    assert len(cards) == 1
    assert cards[0].object_name == "Catalogs.LoyaltyCardsCatalog"
    assert cards[0].requires_manual_verification is True

    assert len(regs) == 1
    assert regs[0].object_name == "AccumulationRegisters.BonusPointsRegister"
    assert regs[0].requires_manual_verification is True
