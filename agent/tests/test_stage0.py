"""Unit tests for Stage 0 Discovery Toolkit (TASK-009 Phase A & FIX-A).

Covers:
- Non-Windows environment returns NOT VERIFIED flags.
- Check-environment never marks metadata discovery VERIFIED.
- FakeMetadataProvider test-only isolation (AGENT_ENV=test required).
- Fake provider never upgrades REAL_* verification flags.
- Sample evidence privacy: zero raw phone/barcode/name/password in aggregates.
- Sanitizer idempotency: sanitize_text output passes scan_for_sensitive_data and validate_safe_output.
- Inventory coverage truthfulness (targeted coverage vs complete root).
- Synthetic example valid under standard validation, but rejected by --require-verified.
- Candidate mapping rejected by --require-verified.
- Verified mapping passes --require-verified.
- Mapping fingerprint calculation and tamper detection.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from poscenter_loyalty_agent.config import AgentSettings
from poscenter_loyalty_agent.main import cli
from poscenter_loyalty_agent.stage0 import (
    FLAG_NOT_VERIFIED,
    FLAG_VERIFIED,
    CandidateDiscoveryHeuristic,
    EnvironmentCheckResult,
    FakeMetadataProvider,
    MetadataField,
    MetadataObject,
    SampleEvidenceBuilder,
    SecuritySanitizerError,
    VerificationFlags,
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
    assert "REAL_ONE_METADATA_DISCOVERY: NOT VERIFIED" in console_text
    assert "REAL_ONE_MAPPING:            NOT VERIFIED" in console_text


def test_check_environment_does_not_mark_metadata_discovery_verified() -> None:
    """Preflight check_environment must NEVER mark REAL_ONE_METADATA_DISCOVERY as VERIFIED."""
    # Simulate a Windows host where COM connector and connection succeed
    mock_connection = MagicMock()
    mock_connection.Metadata = MagicMock()

    mock_connector = MagicMock()
    mock_connector.Connect.return_value = mock_connection

    mock_win32 = MagicMock()
    mock_win32.Dispatch.return_value = mock_connector

    settings = AgentSettings(one_connection_string="Srvr=test;Ref=pilot;Usr=admin;Pwd=secret")

    with patch("sys.platform", "win32"):
        with patch.dict("sys.modules", {"win32com.client": mock_win32, "win32com": MagicMock()}):
            result = check_environment(settings)

            assert result.com_connector_available is True
            assert result.one_connection_successful is True
            assert result.metadata_access_available is True
            # Connector and connection are verified, but metadata discovery MUST remain NOT VERIFIED
            assert result.verification_flags.real_v83_comconnector == FLAG_VERIFIED
            assert result.verification_flags.real_one_connection == FLAG_VERIFIED
            assert result.verification_flags.real_one_metadata_discovery == FLAG_NOT_VERIFIED


def test_fake_provider_restricted_to_test_env(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """--use-fake-provider is rejected with exit code 1 if AGENT_ENV != 'test'."""
    out_dir = tmp_path / "stage0_out"

    # 1. In development -> MUST FAIL
    monkeypatch.setenv("AGENT_ENV", "development")
    with pytest.raises(SystemExit) as exc_info:
        cli(["stage0", "probe-metadata", "--output-dir", str(out_dir), "--use-fake-provider"])
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "--use-fake-provider is strictly restricted to AGENT_ENV='test'" in captured.err
    assert not (out_dir / "metadata_inventory.json").exists()

    # 2. In production -> MUST FAIL
    monkeypatch.setenv("AGENT_ENV", "production")
    monkeypatch.setenv("AGENT_CLOUD_BASE_URL", "https://cloud.poscenter.local")
    monkeypatch.setenv("AGENT_API_KEY", "test_production_api_key_123")
    with pytest.raises(SystemExit) as exc_prod:
        cli(["stage0", "probe-metadata", "--output-dir", str(out_dir), "--use-fake-provider"])
    assert exc_prod.value.code == 1
    assert not (out_dir / "metadata_inventory.json").exists()

    # 3. In test -> SUCCEEDS (does not raise SystemExit)
    monkeypatch.setenv("AGENT_ENV", "test")
    cli(["stage0", "probe-metadata", "--output-dir", str(out_dir), "--use-fake-provider"])
    assert (out_dir / "metadata_inventory.json").exists()
    assert (out_dir / "STAGE0_DISCOVERY_REPORT.md").exists()


def test_fake_provider_never_upgrades_real_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fake metadata provider execution never upgrades REAL_* verification flags."""
    monkeypatch.setenv("AGENT_ENV", "test")
    out_dir = tmp_path / "stage0_flags"

    cli(["stage0", "probe-metadata", "--output-dir", str(out_dir), "--use-fake-provider"])

    report_text = (out_dir / "STAGE0_DISCOVERY_REPORT.md").read_text(encoding="utf-8")
    assert "REAL_WINDOWS_SERVICE: `NOT VERIFIED`" in report_text
    assert "REAL_V83_COMCONNECTOR: `NOT VERIFIED`" in report_text
    assert "REAL_ONE_CONNECTION: `NOT VERIFIED`" in report_text
    assert "REAL_ONE_METADATA_DISCOVERY: `NOT VERIFIED`" in report_text
    assert "REAL_ONE_MAPPING: `NOT VERIFIED`" in report_text


def test_sample_evidence_privacy_secret_person_regression() -> None:
    """SampleEvidenceBuilder retains ZERO raw customer data, phones, barcodes, or passwords."""
    phone = "+77001234567"
    barcode = "0123456789012"
    full_name = "Secret Person"
    connection_fragment = "Pwd=secret"

    builder = SampleEvidenceBuilder()
    builder.observe_card_record(
        barcode=barcode,
        phone=phone,
        full_name=full_name,
        balance=150.50,
    )
    builder.observe_card_record(
        barcode="INVALID_BC",
        phone="123",
        full_name=None,
        balance=-10.0,
    )

    aggregates = builder.build_aggregates()
    serialized = json.dumps(aggregates.model_dump())

    # Regression asserts: raw values strictly absent
    assert full_name not in serialized
    assert phone not in serialized
    assert barcode not in serialized
    assert connection_fragment not in serialized

    # Check safe statistical outputs
    assert aggregates.barcode_aggregate["sample_size"] == 2
    assert aggregates.barcode_aggregate["valid_13_digit"] == 1
    assert aggregates.barcode_aggregate["invalid_count"] == 1
    assert aggregates.phone_aggregate["normalizable_count"] == 1
    assert aggregates.name_aggregate["field_exists"] is True
    assert aggregates.balance_aggregate["allows_negative"] is True

    # Output passes safety scan
    validate_safe_output(serialized, context="SampleEvidenceAggregates")


def test_sanitizer_idempotency_and_safety_scan() -> None:
    """Sanitizer masks secrets cleanly and clean output passes scanner without re-flagging."""
    raw = (
        "Srvr=srv.poscenter.local;Ref=one_pilot;Usr=admin;Pwd=SecretPassword123; "
        "api_key: abc123456789; Phone: +77001234567; Barcode: 0123456789012;"
    )

    clean = sanitize_text(raw)

    # 1. Secrets are gone
    assert "SecretPassword123" not in clean
    assert "abc123456789" not in clean
    assert "+77001234567" not in clean
    assert "0123456789012" not in clean

    # 2. Scanner detects no leaks in cleaned text
    findings = scan_for_sensitive_data(clean)
    assert findings == []
    assert not contains_sensitive_data(clean)

    # 3. validate_safe_output passes
    validate_safe_output(clean, context="SanitizedCleanOutput")

    # 4. Idempotency: second sanitize call produces identical result
    second_clean = sanitize_text(clean)
    assert second_clean == clean


def test_inventory_reports_coverage_truthfully(tmp_path: Path) -> None:
    """Inventory output declares targeted scope and lists unprobed categories truthfully."""
    provider = FakeMetadataProvider()
    inventory = provider.discover_metadata()

    assert inventory.coverage_scope == "targeted_loyalty_core"
    assert "Catalogs" in inventory.probed_categories
    assert "AccumulationRegisters" in inventory.probed_categories
    assert "ChartsOfAccounts" in inventory.unprobed_categories
    assert "Enums" in inventory.unprobed_categories

    _, md_path = write_inventory_reports(inventory, tmp_path)
    md_content = md_path.read_text(encoding="utf-8")

    assert "Targeted Metadata Inventory" in md_content
    assert "Coverage Scope Notice" in md_content
    assert "Probed Categories" in md_content
    assert "Unprobed Categories" in md_content
    assert "ChartsOfAccounts" in md_content


def test_synthetic_example_cannot_pass_require_verified() -> None:
    """agent/stage0_mapping.example.json passes normal validation, but fails --require-verified."""
    example_path = Path("agent/stage0_mapping.example.json")
    assert example_path.exists()

    # Normal validation: PASS
    report_std = validate_mapping(example_path, require_verified=False)
    assert report_std.is_valid is True
    assert report_std.artifact_kind == "synthetic_example"

    # Verified validation: MUST FAIL
    report_ver = validate_mapping(example_path, require_verified=True)
    assert report_ver.is_valid is False
    assert len(report_ver.errors) > 0
    assert any("artifact_kind must be 'real_discovery'" in e for e in report_ver.errors)


def test_candidate_mapping_cannot_pass_require_verified(tmp_path: Path) -> None:
    """Real discovery mapping with CANDIDATE states is rejected by --require-verified."""
    example_path = Path("agent/stage0_mapping.example.json")
    data = json.loads(example_path.read_text(encoding="utf-8"))

    # Switch to real_discovery with real configuration, but leave states as CANDIDATE
    data["artifact_kind"] = "real_discovery"
    data["one_configuration_identity"]["configuration_name"] = "AccountingEnterprise"
    data["mapping_sha256"] = calculate_mapping_fingerprint(data)

    test_file = tmp_path / "candidate_real.json"
    test_file.write_text(json.dumps(data), encoding="utf-8")

    report = validate_mapping(test_file, require_verified=True)
    assert report.is_valid is False
    assert len(report.unverified_fields) > 0
    assert any("cards.barcode_field" in f for f in report.unverified_fields)


def test_all_mandatory_verified_mapping_passes_require_verified(tmp_path: Path) -> None:
    """A genuine real_discovery mapping with all 16 mandatory P0 decisions VERIFIED passes."""
    example_path = Path("agent/stage0_mapping.example.json")
    data = json.loads(example_path.read_text(encoding="utf-8"))

    data["artifact_kind"] = "real_discovery"
    data["one_configuration_identity"]["configuration_name"] = "POSCENTER_RETAIL"
    data["one_configuration_identity"]["platform_version"] = "8.3.24.1342"
    data["one_configuration_identity"]["platform_version_state"] = "VERIFIED"

    # Set real object names and VERIFIED state across cards
    for _k, v in data["cards"].items():
        if isinstance(v, dict) and "state" in v:
            v["state"] = "VERIFIED"
            v["value"] = v["value"].replace("Synthetic", "Real")
            v["evidence"] = ["Inspected in 1C enterprise pilot infobase"]

    # Set real object names and VERIFIED state across transactions
    for k, v in data["transactions"].items():
        if isinstance(v, dict) and "state" in v:
            if k in ("balance_after_field", "receipt_ref_field", "store_field"):
                continue  # Optional fields can remain NOT_STARTED or None
            v["state"] = "VERIFIED"
            if isinstance(v["value"], str):
                v["value"] = v["value"].replace("Synthetic", "Real")
            elif isinstance(v["value"], dict):
                v["value"] = {
                    rk.replace("Synthetic", "Real"): rv.replace("Synthetic", "Real")
                    for rk, rv in v["value"].items()
                }
            v["evidence"] = ["Verified against pilot movements data"]

    # Set cursor strategy to VERIFIED
    data["cursor_strategy"]["cards"]["state"] = "VERIFIED"
    data["cursor_strategy"]["cards"]["value"]["strategy_name"] = "keyset_timestamp_ref"
    data["cursor_strategy"]["cards"]["value"]["ordering_fields"] = ["ModifiedAt", "Ref"]
    data["cursor_strategy"]["cards"]["value"]["tie_breaker"] = "Ref"
    data["cursor_strategy"]["cards"]["evidence"] = ["Deterministic keyset order verified"]

    data["cursor_strategy"]["transactions"]["state"] = "VERIFIED"
    data["cursor_strategy"]["transactions"]["value"]["strategy_name"] = "keyset_period_recorder"
    data["cursor_strategy"]["transactions"]["value"]["ordering_fields"] = ["Period", "Recorder"]
    data["cursor_strategy"]["transactions"]["value"]["tie_breaker"] = "LineNumber"
    data["cursor_strategy"]["transactions"]["evidence"] = ["Deterministic register order verified"]

    # Recalculate fingerprint
    data["mapping_sha256"] = calculate_mapping_fingerprint(data)

    test_file = tmp_path / "verified_real_mapping.json"
    test_file.write_text(json.dumps(data), encoding="utf-8")

    report = validate_mapping(test_file, require_verified=True)
    assert report.is_valid is True, f"Validation failed: {report.errors}"
    assert report.require_verified is True
    assert len(report.unverified_fields) == 0


def test_mapping_fingerprint_tamper_detection(tmp_path: Path) -> None:
    """Tampering with any mapped character invalidates fingerprint check."""
    example_path = Path("agent/stage0_mapping.example.json")
    data = json.loads(example_path.read_text(encoding="utf-8"))

    orig_fp = data["mapping_sha256"]
    # Alter one character
    data["cards"]["barcode_field"]["value"] = "TamperedField"
    # Keep original hash
    data["mapping_sha256"] = orig_fp

    test_file = tmp_path / "tampered.json"
    test_file.write_text(json.dumps(data), encoding="utf-8")

    report = validate_mapping(test_file)
    assert not report.is_valid
    assert any("Fingerprint mismatch" in e for e in report.errors)


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
    assert regs[0].role == "balance_source_candidate"


def test_security_sanitizer_error_raised(tmp_path: Path) -> None:
    """Unsanitized text with credentials raises SecuritySanitizerError on output validation."""
    dirty_content = "Connection: Usr=admin;Pwd=clear_text_password; Phone: +77019998877"
    with pytest.raises(SecuritySanitizerError) as exc_info:
        validate_safe_output(dirty_content, context="UnsafeArtifact")
    assert "Security safety violation" in str(exc_info.value)

    env_result = check_environment()
    env_path = write_environment_report(env_result, tmp_path)
    assert env_path.exists()

    summary_path = write_discovery_summary_report(env_result, None, tmp_path)
    assert summary_path.exists()


def test_real_probe_success_updates_environment_json_and_report(tmp_path: Path) -> None:
    """Successful real COM probe elevates real_one_metadata_discovery in both environment.json and report."""
    out_dir = tmp_path / "stage0_real_success"

    env_mock = EnvironmentCheckResult(
        platform="win32",
        is_windows=True,
        pywin32_available=True,
        com_connector_available=True,
        connection_string_configured=True,
        one_connection_successful=True,
        metadata_access_available=True,
        verification_flags=VerificationFlags(
            real_windows_service=FLAG_NOT_VERIFIED,
            real_v83_comconnector=FLAG_VERIFIED,
            real_one_connection=FLAG_VERIFIED,
            real_one_metadata_discovery=FLAG_NOT_VERIFIED,
            real_one_mapping=FLAG_NOT_VERIFIED,
        ),
        details=["1C COM connection established."],
    )

    mock_provider = MagicMock()
    mock_provider.discover_metadata.return_value = FakeMetadataProvider().discover_metadata()

    with patch("poscenter_loyalty_agent.stage0.cli.check_environment", return_value=env_mock):
        with patch("poscenter_loyalty_agent.stage0.cli.ComMetadataProvider", return_value=mock_provider):
            cli(["stage0", "probe-metadata", "--output-dir", str(out_dir)])

    # 1. Check environment.json: MUST have real_one_metadata_discovery = VERIFIED
    env_json_path = out_dir / "environment.json"
    assert env_json_path.exists()
    env_data = json.loads(env_json_path.read_text(encoding="utf-8"))
    flags = env_data["verification_flags"]
    assert flags["real_v83_comconnector"] == FLAG_VERIFIED
    assert flags["real_one_connection"] == FLAG_VERIFIED
    assert flags["real_one_metadata_discovery"] == FLAG_VERIFIED
    assert flags["real_one_mapping"] == FLAG_NOT_VERIFIED

    # 2. Check STAGE0_DISCOVERY_REPORT.md: MUST reflect identical states
    report_path = out_dir / "STAGE0_DISCOVERY_REPORT.md"
    assert report_path.exists()
    report_text = report_path.read_text(encoding="utf-8")
    assert f"REAL_V83_COMCONNECTOR: `{FLAG_VERIFIED}`" in report_text
    assert f"REAL_ONE_CONNECTION: `{FLAG_VERIFIED}`" in report_text
    assert f"REAL_ONE_METADATA_DISCOVERY: `{FLAG_VERIFIED}`" in report_text
    assert f"REAL_ONE_MAPPING: `{FLAG_NOT_VERIFIED}`" in report_text


def test_real_probe_failure_leaves_environment_json_not_verified(tmp_path: Path) -> None:
    """When real COM metadata probe raises an exception, metadata discovery remains NOT VERIFIED."""
    out_dir = tmp_path / "stage0_real_fail"

    env_mock = EnvironmentCheckResult(
        platform="win32",
        is_windows=True,
        pywin32_available=True,
        com_connector_available=True,
        connection_string_configured=True,
        one_connection_successful=True,
        metadata_access_available=True,
        verification_flags=VerificationFlags(
            real_v83_comconnector=FLAG_VERIFIED,
            real_one_connection=FLAG_VERIFIED,
            real_one_metadata_discovery=FLAG_NOT_VERIFIED,
            real_one_mapping=FLAG_NOT_VERIFIED,
        ),
        details=["1C COM connection established."],
    )

    mock_provider = MagicMock()
    mock_provider.discover_metadata.side_effect = RuntimeError("COM connection dropped during metadata enumeration")

    with patch("poscenter_loyalty_agent.stage0.cli.check_environment", return_value=env_mock):
        with patch("poscenter_loyalty_agent.stage0.cli.ComMetadataProvider", return_value=mock_provider):
            with pytest.raises(SystemExit) as exc_info:
                cli(["stage0", "probe-metadata", "--output-dir", str(out_dir)])
            assert exc_info.value.code == 1

    # Check environment.json still exists and has NOT VERIFIED
    env_json_path = out_dir / "environment.json"
    assert env_json_path.exists()
    env_data = json.loads(env_json_path.read_text(encoding="utf-8"))
    assert env_data["verification_flags"]["real_one_metadata_discovery"] == FLAG_NOT_VERIFIED

    report_text = (out_dir / "STAGE0_DISCOVERY_REPORT.md").read_text(encoding="utf-8")
    assert f"REAL_ONE_METADATA_DISCOVERY: `{FLAG_NOT_VERIFIED}`" in report_text


def test_real_probe_sanitizer_failure_leaves_not_verified(tmp_path: Path) -> None:
    """If inventory output safety check fails, metadata discovery remains NOT VERIFIED."""
    out_dir = tmp_path / "stage0_sanitizer_fail"

    env_mock = EnvironmentCheckResult(
        platform="win32",
        is_windows=True,
        pywin32_available=True,
        com_connector_available=True,
        connection_string_configured=True,
        one_connection_successful=True,
        metadata_access_available=True,
        verification_flags=VerificationFlags(
            real_v83_comconnector=FLAG_VERIFIED,
            real_one_connection=FLAG_VERIFIED,
            real_one_metadata_discovery=FLAG_NOT_VERIFIED,
            real_one_mapping=FLAG_NOT_VERIFIED,
        ),
        details=["1C COM connection established."],
    )

    # Return inventory that has clear-text password in synonym (violates validate_safe_output)
    dirty_inventory = FakeMetadataProvider().discover_metadata()
    dirty_inventory.objects[0].synonym = "Object with Pwd=clear_secret_password"

    mock_provider = MagicMock()
    mock_provider.discover_metadata.return_value = dirty_inventory

    with patch("poscenter_loyalty_agent.stage0.cli.check_environment", return_value=env_mock):
        with patch("poscenter_loyalty_agent.stage0.cli.ComMetadataProvider", return_value=mock_provider):
            with pytest.raises(SystemExit) as exc_info:
                cli(["stage0", "probe-metadata", "--output-dir", str(out_dir)])
            assert exc_info.value.code == 1

    env_json_path = out_dir / "environment.json"
    assert env_json_path.exists()
    env_data = json.loads(env_json_path.read_text(encoding="utf-8"))
    assert env_data["verification_flags"]["real_one_metadata_discovery"] == FLAG_NOT_VERIFIED


def test_verified_mapping_empty_evidence_rejected(tmp_path: Path) -> None:
    """A mandatory P0 field with state=VERIFIED and empty evidence list is rejected by --require-verified."""
    example_path = Path("agent/stage0_mapping.example.json")
    data = json.loads(example_path.read_text(encoding="utf-8"))

    data["artifact_kind"] = "real_discovery"
    data["one_configuration_identity"]["configuration_name"] = "POSCENTER_RETAIL"
    data["one_configuration_identity"]["platform_version"] = "8.3.24.1342"
    data["one_configuration_identity"]["platform_version_state"] = "VERIFIED"

    for _k, v in data["cards"].items():
        if isinstance(v, dict) and "state" in v:
            v["state"] = "VERIFIED"
            v["value"] = v["value"].replace("Synthetic", "Real")
            v["evidence"] = ["Valid evidence string from pilot database"]

    for _k, v in data["transactions"].items():
        if isinstance(v, dict) and "state" in v:
            if _k in ("balance_after_field", "receipt_ref_field", "store_field"):
                continue
            v["state"] = "VERIFIED"
            if isinstance(v["value"], str):
                v["value"] = v["value"].replace("Synthetic", "Real")
            elif isinstance(v["value"], dict):
                v["value"] = {
                    rk.replace("Synthetic", "Real"): rv.replace("Synthetic", "Real")
                    for rk, rv in v["value"].items()
                }
            v["evidence"] = ["Valid movement evidence from pilot database"]

    data["cursor_strategy"]["cards"]["state"] = "VERIFIED"
    data["cursor_strategy"]["cards"]["value"]["strategy_name"] = "keyset_timestamp_ref"
    data["cursor_strategy"]["cards"]["value"]["ordering_fields"] = ["ModifiedAt", "Ref"]
    data["cursor_strategy"]["cards"]["value"]["tie_breaker"] = "Ref"
    data["cursor_strategy"]["cards"]["evidence"] = ["Keyset evidence"]

    data["cursor_strategy"]["transactions"]["state"] = "VERIFIED"
    data["cursor_strategy"]["transactions"]["value"]["strategy_name"] = "keyset_period_recorder"
    data["cursor_strategy"]["transactions"]["value"]["ordering_fields"] = ["Period", "Recorder"]
    data["cursor_strategy"]["transactions"]["value"]["tie_breaker"] = "LineNumber"
    data["cursor_strategy"]["transactions"]["evidence"] = ["Keyset evidence"]

    # Now empty out evidence for cards.barcode_field
    data["cards"]["barcode_field"]["evidence"] = []
    data["mapping_sha256"] = calculate_mapping_fingerprint(data)

    test_file = tmp_path / "empty_evidence_mapping.json"
    test_file.write_text(json.dumps(data), encoding="utf-8")

    report = validate_mapping(test_file, require_verified=True)
    assert report.is_valid is False
    assert "cards.barcode_field" in report.unverified_fields
    assert any(
        "Mandatory mapping field 'cards.barcode_field' is VERIFIED but has no verification evidence" in e
        for e in report.errors
    )


def test_verified_mapping_whitespace_evidence_rejected(tmp_path: Path) -> None:
    """A mandatory P0 field with state=VERIFIED and whitespace-only evidence is rejected."""
    example_path = Path("agent/stage0_mapping.example.json")
    data = json.loads(example_path.read_text(encoding="utf-8"))

    data["artifact_kind"] = "real_discovery"
    data["one_configuration_identity"]["configuration_name"] = "POSCENTER_RETAIL"
    data["one_configuration_identity"]["platform_version"] = "8.3.24.1342"
    data["one_configuration_identity"]["platform_version_state"] = "VERIFIED"

    for _k, v in data["cards"].items():
        if isinstance(v, dict) and "state" in v:
            v["state"] = "VERIFIED"
            v["value"] = v["value"].replace("Synthetic", "Real")
            v["evidence"] = ["Valid evidence from pilot database"]

    for _k, v in data["transactions"].items():
        if isinstance(v, dict) and "state" in v:
            if _k in ("balance_after_field", "receipt_ref_field", "store_field"):
                continue
            v["state"] = "VERIFIED"
            if isinstance(v["value"], str):
                v["value"] = v["value"].replace("Synthetic", "Real")
            elif isinstance(v["value"], dict):
                v["value"] = {
                    rk.replace("Synthetic", "Real"): rv.replace("Synthetic", "Real")
                    for rk, rv in v["value"].items()
                }
            v["evidence"] = ["Valid evidence from pilot database"]

    data["cursor_strategy"]["cards"]["state"] = "VERIFIED"
    data["cursor_strategy"]["cards"]["value"]["strategy_name"] = "keyset_timestamp_ref"
    data["cursor_strategy"]["cards"]["value"]["ordering_fields"] = ["ModifiedAt", "Ref"]
    data["cursor_strategy"]["cards"]["value"]["tie_breaker"] = "Ref"
    data["cursor_strategy"]["cards"]["evidence"] = ["Keyset evidence"]

    data["cursor_strategy"]["transactions"]["state"] = "VERIFIED"
    data["cursor_strategy"]["transactions"]["value"]["strategy_name"] = "keyset_period_recorder"
    data["cursor_strategy"]["transactions"]["value"]["ordering_fields"] = ["Period", "Recorder"]
    data["cursor_strategy"]["transactions"]["value"]["tie_breaker"] = "LineNumber"
    data["cursor_strategy"]["transactions"]["evidence"] = ["Keyset evidence"]

    # Whitespace only evidence
    data["cards"]["barcode_field"]["evidence"] = ["   ", "\t\n  "]
    data["mapping_sha256"] = calculate_mapping_fingerprint(data)

    test_file = tmp_path / "whitespace_evidence_mapping.json"
    test_file.write_text(json.dumps(data), encoding="utf-8")

    report = validate_mapping(test_file, require_verified=True)
    assert report.is_valid is False
    assert "cards.barcode_field" in report.unverified_fields
    assert any(
        "Mandatory mapping field 'cards.barcode_field' is VERIFIED but has no verification evidence" in e
        for e in report.errors
    )


def test_zero_speculative_assumptions_in_stage0_sources() -> None:
    """Stage 0 production sources and example mapping must contain zero speculative markers."""
    stage0_dir = Path("agent/src/poscenter_loyalty_agent/stage0")
    assert stage0_dir.exists()

    forbidden_markers = [
        "Catalogs.InformationCards",
        "InformationCards",
        "AccumulationRegisters.BonusPoints",
        "BonusPoints",
        "EAN-13",
        "13-digit EAN",
        "accrual",
        "redemption",
        "Ref / UUID",
    ]

    for py_file in stage0_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for marker in forbidden_markers:
            assert marker not in content, f"Forbidden speculative marker '{marker}' found in {py_file}"

    # Also check stage0_mapping.example.json
    example_path = Path("agent/stage0_mapping.example.json")
    example_content = example_path.read_text(encoding="utf-8")
    for marker in forbidden_markers:
        assert marker not in example_content, f"Forbidden speculative marker '{marker}' found in {example_path}"


def test_zero_speculative_semantic_phrases_in_stage0_and_reports(tmp_path: Path) -> None:
    """Stage 0 sources and generated discovery reports must contain zero speculative semantic phrases."""
    stage0_dir = Path("agent/src/poscenter_loyalty_agent/stage0")
    assert stage0_dir.exists()

    forbidden_semantic_phrases = [
        "accumulation register or balance source",
        "deletion mark or blocked flag",
        "bonus movement document/register",
        "1C movement types",
        "retail point / store link",
        "Register or attribute supplying",
        "blocked / deletion mark",
        "Store / retail point reference",
    ]

    for py_file in stage0_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for phrase in forbidden_semantic_phrases:
            assert (
                phrase.lower() not in content.lower()
            ), f"Forbidden semantic phrase '{phrase}' found in source {py_file}"

    # Also verify generated synthetic discovery reports
    provider = FakeMetadataProvider()
    inventory = provider.discover_metadata()
    env_result = check_environment()

    out_dir = tmp_path / "zero_assumption_reports"
    write_inventory_reports(inventory, out_dir)
    write_discovery_summary_report(env_result, inventory, out_dir)
    write_discovery_summary_report(env_result, None, out_dir / "unconnected")

    for report_file in out_dir.rglob("*.*"):
        if report_file.is_file():
            content = report_file.read_text(encoding="utf-8")
            for phrase in forbidden_semantic_phrases:
                assert (
                    phrase.lower() not in content.lower()
                ), f"Forbidden semantic phrase '{phrase}' found in report artifact {report_file}"




