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
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from poscenter_loyalty_agent.config import AgentSettings
from poscenter_loyalty_agent.main import cli
from poscenter_loyalty_agent.stage0 import (
    FLAG_NOT_VERIFIED,
    FLAG_VERIFIED,
    CandidateDiscoveryHeuristic,
    ComMetadataProvider,
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

TESTS_DIR = Path(__file__).resolve().parent
AGENT_DIR = TESTS_DIR.parent
REPO_ROOT = AGENT_DIR.parent

EXAMPLE_MAPPING = AGENT_DIR / "stage0_mapping.example.json"
STAGE0_SRC_DIR = AGENT_DIR / "src" / "poscenter_loyalty_agent" / "stage0"
RUNBOOK_PATH = REPO_ROOT / "docs" / "STAGE0_WINDOWS_RUNBOOK.md"


def test_non_windows_environment_reports_not_verified() -> None:
    """On non-Windows hosts, environment check safely reports NOT VERIFIED flags without errors."""
    with patch("sys.platform", "linux"):
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


def test_fake_provider_run_does_not_call_real_one_connect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fake provider run must never attempt COM connect even if ONE_CONNECTION_STRING is present."""
    monkeypatch.setenv("AGENT_ENV", "test")
    monkeypatch.setenv("ONE_CONNECTION_STRING", "Srvr=fake;Ref=fake;Usr=fake;Pwd=fake")
    out_dir = tmp_path / "stage0_fake_probe"

    mock_connection = MagicMock()
    mock_connection.Metadata = MagicMock()

    mock_connector = MagicMock()
    mock_connector.Connect.return_value = mock_connection

    mock_win32 = MagicMock()
    mock_win32.Dispatch.return_value = mock_connector

    with patch("sys.platform", "win32"):
        with patch.dict("sys.modules", {"win32com.client": mock_win32, "win32com": MagicMock(client=mock_win32)}):
            cli(["stage0", "probe-metadata", "--output-dir", str(out_dir), "--use-fake-provider"])

    mock_connector.Connect.assert_not_called()
    report_text = (out_dir / "STAGE0_DISCOVERY_REPORT.md").read_text(encoding="utf-8")
    assert "REAL_WINDOWS_SERVICE: `NOT VERIFIED`" in report_text
    assert "REAL_V83_COMCONNECTOR: `NOT VERIFIED`" in report_text
    assert "REAL_ONE_CONNECTION: `NOT VERIFIED`" in report_text
    assert "REAL_ONE_METADATA_DISCOVERY: `NOT VERIFIED`" in report_text
    assert "REAL_ONE_MAPPING: `NOT VERIFIED`" in report_text


def test_com_metadata_provider_probes_enums_register_kind_and_tabular_sections() -> None:
    """ComMetadataProvider discovers Enums, register_kind, tabular sections, and converts types via conn.String."""
    mock_conn = MagicMock()

    def fake_string(obj: Any) -> str:
        if obj == "type_err":
            raise RuntimeError("COM String conversion error")
        return f"String({obj})"

    mock_conn.String.side_effect = fake_string

    # 1. Catalog with TabularSection attributes
    cat_attr = MagicMock()
    cat_attr.Name = "Code"
    cat_attr.Synonym = "CatalogCode"
    cat_attr.Type = "String(10)"

    tab_attr = MagicMock()
    tab_attr.Name = "LineBonus"
    tab_attr.Synonym = "BonusInLine"
    tab_attr.Type = "Number(10,2)"

    tab_section = MagicMock()
    tab_section.Name = "Goods"
    tab_section.Attributes.Count.return_value = 1
    tab_section.Attributes.Get.return_value = tab_attr

    cat_obj = MagicMock()
    cat_obj.Name = "BonusCards"
    cat_obj.Synonym = "CardsSynonym"
    cat_obj.Attributes.Count.return_value = 1
    cat_obj.Attributes.Get.return_value = cat_attr
    cat_obj.Dimensions.Count.return_value = 0
    cat_obj.Resources.Count.return_value = 0
    cat_obj.TabularSections.Count.return_value = 1
    cat_obj.TabularSections.Get.return_value = tab_section

    # 2. AccumulationRegister with RegisterType and type error
    acc_dim = MagicMock()
    acc_dim.Name = "Card"
    acc_dim.Synonym = "CardDim"
    acc_dim.Type = "type_err"

    acc_res = MagicMock()
    acc_res.Name = "Balance"
    acc_res.Synonym = "BalanceRes"
    acc_res.Type = "Number(15,2)"

    acc_obj = MagicMock()
    acc_obj.Name = "BonusBalances"
    acc_obj.Synonym = "BalancesSynonym"
    acc_obj.RegisterType = "Balances"
    acc_obj.Attributes.Count.return_value = 0
    acc_obj.Dimensions.Count.return_value = 1
    acc_obj.Dimensions.Get.return_value = acc_dim
    acc_obj.Resources.Count.return_value = 1
    acc_obj.Resources.Get.return_value = acc_res
    acc_obj.TabularSections.Count.return_value = 0

    # 3. InformationRegister with InformationRegisterPeriodicity
    info_dim = MagicMock()
    info_dim.Name = "PeriodDim"
    info_dim.Synonym = "PeriodSyn"
    info_dim.Type = "Date"

    info_obj = MagicMock()
    info_obj.Name = "StatusHistory"
    info_obj.Synonym = "StatusHistorySynonym"
    info_obj.InformationRegisterPeriodicity = "Day"
    info_obj.Attributes.Count.return_value = 0
    info_obj.Dimensions.Count.return_value = 1
    info_obj.Dimensions.Get.return_value = info_dim
    info_obj.Resources.Count.return_value = 0
    info_obj.TabularSections.Count.return_value = 0

    # 4. Document
    doc_obj = MagicMock()
    doc_obj.Name = "SalesCheck"
    doc_obj.Synonym = "SalesCheckSynonym"
    doc_obj.Attributes.Count.return_value = 0
    doc_obj.Dimensions.Count.return_value = 0
    doc_obj.Resources.Count.return_value = 0
    doc_obj.TabularSections.Count.return_value = 0

    # 5. Enums with EnumValues
    enum_val1 = MagicMock()
    enum_val1.Name = "Active"
    enum_val1.Synonym = "ActiveState"

    enum_val2 = MagicMock()
    enum_val2.Name = "Blocked"
    enum_val2.Synonym = "BlockedState"

    enum_obj = MagicMock()
    enum_obj.Name = "CardStates"
    enum_obj.Synonym = "CardStatesSynonym"
    enum_obj.EnumValues.Count.return_value = 2
    enum_obj.EnumValues.Get.side_effect = [enum_val1, enum_val2]

    # Meta collections
    meta = MagicMock()
    meta.Name = "TestLoyaltyConfig"
    meta.Version = "2.0.1"

    meta.Catalogs.Count.return_value = 1
    meta.Catalogs.Get.return_value = cat_obj

    meta.AccumulationRegisters.Count.return_value = 1
    meta.AccumulationRegisters.Get.return_value = acc_obj

    meta.InformationRegisters.Count.return_value = 1
    meta.InformationRegisters.Get.return_value = info_obj

    meta.Documents.Count.return_value = 1
    meta.Documents.Get.return_value = doc_obj

    meta.Enums.Count.return_value = 1
    meta.Enums.Get.return_value = enum_obj

    mock_conn.Metadata = meta

    provider = ComMetadataProvider("Srvr=mock;Ref=mock")
    with patch.object(provider.connector, "connect", return_value=mock_conn):
        with patch.object(provider.connector, "disconnect"):
            inventory = provider.discover_metadata()

    assert inventory.configuration.configuration_name == "TestLoyaltyConfig"

    cat_res = next(o for o in inventory.objects if o.category == "Catalogs")
    assert cat_res.name == "BonusCards"
    assert cat_res.tabular_sections == ["Goods"]
    attr_field = next(f for f in cat_res.fields if f.name == "Code")
    assert attr_field.type_desc == "String(String(10))"
    tab_field = next(f for f in cat_res.fields if f.name == "Goods.LineBonus")
    assert tab_field.synonym == "BonusInLine"
    assert tab_field.type_desc == "String(Number(10,2))"

    acc_res_obj = next(o for o in inventory.objects if o.category == "AccumulationRegisters")
    assert acc_res_obj.name == "BonusBalances"
    assert acc_res_obj.register_kind == "String(Balances)"
    dim_field = next(f for f in acc_res_obj.fields if f.name == "Card")
    assert dim_field.type_desc == "Unknown"
    assert dim_field.is_dimension is True

    info_res_obj = next(o for o in inventory.objects if o.category == "InformationRegisters")
    assert info_res_obj.name == "StatusHistory"
    assert info_res_obj.register_kind == "String(Day)"

    enum_res_obj = next(o for o in inventory.objects if o.category == "Enums")
    assert enum_res_obj.name == "CardStates"
    assert len(enum_res_obj.fields) == 2
    assert enum_res_obj.fields[0].name == "Active"
    assert enum_res_obj.fields[0].type_desc == "EnumValue"
    assert enum_res_obj.fields[1].name == "Blocked"
    assert enum_res_obj.fields[1].type_desc == "EnumValue"



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
    assert "Enums" in inventory.probed_categories
    assert "ChartsOfAccounts" in inventory.unprobed_categories
    assert "Enums" not in inventory.unprobed_categories

    _, md_path = write_inventory_reports(inventory, tmp_path)
    md_content = md_path.read_text(encoding="utf-8")

    assert "Targeted Metadata Inventory" in md_content
    assert "Coverage Scope Notice" in md_content
    assert "Probed Categories" in md_content
    assert "Unprobed Categories" in md_content
    assert "ChartsOfAccounts" in md_content


def test_synthetic_example_cannot_pass_require_verified() -> None:
    """agent/stage0_mapping.example.json passes normal validation, but fails --require-verified."""
    example_path = EXAMPLE_MAPPING
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
    example_path = EXAMPLE_MAPPING
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
    example_path = EXAMPLE_MAPPING
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
    example_path = EXAMPLE_MAPPING
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
    example_path = EXAMPLE_MAPPING
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
    example_path = EXAMPLE_MAPPING
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
    stage0_dir = STAGE0_SRC_DIR
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
    example_path = EXAMPLE_MAPPING
    example_content = example_path.read_text(encoding="utf-8")
    for marker in forbidden_markers:
        assert marker not in example_content, f"Forbidden speculative marker '{marker}' found in {example_path}"


def test_zero_speculative_semantic_phrases_in_stage0_and_reports(tmp_path: Path) -> None:
    """Stage 0 sources and generated discovery reports must contain zero speculative semantic phrases."""
    stage0_dir = STAGE0_SRC_DIR
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
        "Dimension or requisite linking",
        "Field storing transaction bonus amount",
        "Movement timestamp field",
        "Field storing balance after movement",
        "REAL_WINDOWS_SERVICE:        VERIFIED (or Windows host confirmed)",
        "REAL_WINDOWS_SERVICE: VERIFIED (or Windows host confirmed)",
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

    # Also verify Windows Runbook documentation
    if RUNBOOK_PATH.exists():
        runbook_content = RUNBOOK_PATH.read_text(encoding="utf-8")
        for phrase in forbidden_semantic_phrases:
            assert (
                phrase.lower() not in runbook_content.lower()
            ), f"Forbidden semantic phrase '{phrase}' found in runbook {RUNBOOK_PATH}"


def test_cmd_probe_metadata_real_path_makes_exactly_one_connect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """In real execution path on mocked COM, probe-metadata makes exactly ONE Connect() call."""
    out_dir = tmp_path / "single_connect"
    monkeypatch.setenv("AGENT_ENV", "development")
    monkeypatch.setenv("ONE_CONNECTION_STRING", "Srvr=fake;Ref=fake;Usr=fake;Pwd=fake")

    mock_connection = MagicMock()
    meta = MagicMock()
    meta.Name = "MockConfiguration"
    meta.Version = "1.0.0"
    for cat in ("Catalogs", "AccumulationRegisters", "InformationRegisters", "Documents", "Enums"):
        coll = MagicMock()
        coll.Count.return_value = 0
        setattr(meta, cat, coll)
    mock_connection.Metadata = meta

    mock_connector = MagicMock()
    mock_connector.Connect.return_value = mock_connection

    mock_win32 = MagicMock()
    mock_win32.Dispatch.return_value = mock_connector

    with patch("sys.platform", "win32"):
        with patch.dict("sys.modules", {"win32com.client": mock_win32, "win32com": MagicMock(client=mock_win32)}):
            cli(["stage0", "probe-metadata", "--output-dir", str(out_dir)])

    mock_connector.Connect.assert_called_once()
    assert (out_dir / "environment.json").exists()
    assert (out_dir / "metadata_inventory.json").exists()
    assert (out_dir / "STAGE0_DISCOVERY_REPORT.md").exists()


def test_release_connection_clears_active_and_excludes_from_json(tmp_path: Path) -> None:
    """release_connection() zeroes active_connection; active_connection is excluded from serialization and JSON."""
    mock_conn = MagicMock()
    env = EnvironmentCheckResult(
        platform="win32",
        is_windows=True,
        pywin32_available=True,
        com_connector_available=True,
        connection_string_configured=True,
        one_connection_successful=True,
        metadata_access_available=True,
        verification_flags=VerificationFlags(),
        details=["test details"],
        active_connection=mock_conn,
    )
    assert env.active_connection is mock_conn

    # 1. Verify excluded from model_dump()
    dumped = env.model_dump()
    assert "active_connection" not in dumped

    # 2. Verify excluded from written environment.json
    out_file = write_environment_report(env, tmp_path)
    content = json.loads(out_file.read_text(encoding="utf-8"))
    assert "active_connection" not in content

    # 3. Verify release_connection() clears active_connection
    env.release_connection()
    assert env.active_connection is None


def test_com_metadata_provider_extracts_standard_attributes_and_catalog_props(tmp_path: Path) -> None:
    """ComMetadataProvider extracts StandardAttributes via iteration and catalog_props, and writes them to reports."""
    mock_conn = MagicMock()
    mock_conn.String.side_effect = lambda x: f"Str({x})"

    # 1. Catalog with StandardAttributes (iterable) and catalog props
    cat_std1 = MagicMock()
    cat_std1.Name = "Ref"
    cat_std1.Synonym = "Ссылка"
    cat_std1.Type = "CatalogRef"

    cat_std2 = MagicMock()
    cat_std2.Name = "Code"
    cat_std2.Synonym = "Код"
    cat_std2.Type = "String(13)"

    cat_obj = MagicMock()
    cat_obj.Name = "BonusCards"
    cat_obj.Synonym = "Бонусные карты"
    cat_obj.CodeLength = 13
    cat_obj.CodeType = "String"
    cat_obj.DescriptionLength = 50
    cat_obj.Hierarchical = False

    cat_obj.StandardAttributes = [cat_std1, cat_std2]
    cat_obj.Attributes.Count.return_value = 0
    cat_obj.Dimensions.Count.return_value = 0
    cat_obj.Resources.Count.return_value = 0
    cat_obj.TabularSections.Count.return_value = 0

    # 2. Document with StandardAttributes (iterable)
    doc_std1 = MagicMock()
    doc_std1.Name = "Number"
    doc_std1.Synonym = "Номер"
    doc_std1.Type = "String(11)"

    doc_obj = MagicMock()
    doc_obj.Name = "SalesCheck"
    doc_obj.Synonym = "Чек"
    doc_obj.StandardAttributes = [doc_std1]
    doc_obj.Attributes.Count.return_value = 0
    doc_obj.Dimensions.Count.return_value = 0
    doc_obj.Resources.Count.return_value = 0
    doc_obj.TabularSections.Count.return_value = 0

    meta = MagicMock()
    meta.Name = "TestConfig"
    meta.Version = "1.0.0"
    meta.Catalogs.Count.return_value = 1
    meta.Catalogs.Get.return_value = cat_obj
    meta.Documents.Count.return_value = 1
    meta.Documents.Get.return_value = doc_obj
    meta.AccumulationRegisters.Count.return_value = 0
    meta.InformationRegisters.Count.return_value = 0
    meta.Enums.Count.return_value = 0

    mock_conn.Metadata = meta

    provider = ComMetadataProvider("Srvr=mock;Ref=mock")
    with patch.object(provider.connector, "connect", return_value=mock_conn):
        with patch.object(provider.connector, "disconnect"):
            inventory = provider.discover_metadata()

    cat_item = next(o for o in inventory.objects if o.category == "Catalogs")
    assert cat_item.catalog_props == {
        "CodeLength": "Str(13)",
        "CodeType": "Str(String)",
        "DescriptionLength": "Str(50)",
        "Hierarchical": "Str(False)",
    }
    assert len(cat_item.fields) == 2
    assert cat_item.fields[0].name == "Ref"
    assert cat_item.fields[0].kind == "StandardAttribute"
    assert cat_item.fields[1].name == "Code"
    assert cat_item.fields[1].kind == "StandardAttribute"

    doc_item = next(o for o in inventory.objects if o.category == "Documents")
    assert len(doc_item.fields) == 1
    assert doc_item.fields[0].name == "Number"
    assert doc_item.fields[0].kind == "StandardAttribute"

    # Test report formatting
    _, md_path = write_inventory_reports(inventory, tmp_path)
    md_content = md_path.read_text(encoding="utf-8")
    assert "StandardAttribute" in md_content
    assert "Catalog Properties:" in md_content
    assert "CodeLength: `Str(13)`" in md_content


def test_com_metadata_provider_standard_attributes_exception_handled_with_unavailable_flag() -> None:
    """When iterating StandardAttributes raises an exception, discover_metadata records unavailable flag and succeeds."""
    mock_conn = MagicMock()
    mock_conn.String.side_effect = str

    class ExplodingCollection:
        def __iter__(self):
            raise TypeError("Iteration not supported")

    cat_obj = MagicMock()
    cat_obj.Name = "ExplodingCatalog"
    cat_obj.Synonym = "Ошибочный справочник"
    cat_obj.CodeLength = 10
    cat_obj.CodeType = "String"
    cat_obj.DescriptionLength = 25
    cat_obj.Hierarchical = False
    cat_obj.StandardAttributes = ExplodingCollection()
    cat_obj.Attributes.Count.return_value = 0
    cat_obj.Dimensions.Count.return_value = 0
    cat_obj.Resources.Count.return_value = 0
    cat_obj.TabularSections.Count.return_value = 0

    meta = MagicMock()
    meta.Name = "TestConfig"
    meta.Version = "1.0.0"
    meta.Catalogs.Count.return_value = 1
    meta.Catalogs.Get.return_value = cat_obj
    meta.Documents.Count.return_value = 0
    meta.AccumulationRegisters.Count.return_value = 0
    meta.InformationRegisters.Count.return_value = 0
    meta.Enums.Count.return_value = 0

    mock_conn.Metadata = meta

    provider = ComMetadataProvider("Srvr=mock;Ref=mock")
    with patch.object(provider.connector, "connect", return_value=mock_conn):
        with patch.object(provider.connector, "disconnect"):
            inventory = provider.discover_metadata()

    cat_item = next(o for o in inventory.objects if o.category == "Catalogs")
    assert cat_item.catalog_props is not None
    assert cat_item.catalog_props["standard_attributes"] == "unavailable: TypeError"
    assert cat_item.catalog_props["CodeLength"] == "10"


def test_cmd_profile_data_fake_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """stage0 profile-data --use-fake-provider generates sanitized reports without COM."""
    monkeypatch.setenv("AGENT_ENV", "test")
    out_dir = tmp_path / "fake_profile"
    cli(["stage0", "profile-data", "--output-dir", str(out_dir), "--use-fake-provider"])
    assert (out_dir / "data_profile.json").exists()
    assert (out_dir / "data_profile.md").exists()

    md = (out_dir / "data_profile.md").read_text(encoding="utf-8")
    assert "POSCENTER ONE Data Profile Report" in md
    assert "Выводы для Технического Задания" in md


def test_data_profile_leaks_zero_mock_data_and_profiles_accurately(tmp_path: Path) -> None:
    """collect_data_profile retains ZERO raw customer data, codes, barcodes, or phones."""
    from poscenter_loyalty_agent.stage0.data_profile import (
        collect_data_profile,
        write_data_profile_reports,
    )

    mock_conn = MagicMock()
    mock_conn.String.side_effect = lambda x: f"Str({x})"

    secret_barcode = "7770001234567"
    secret_code = "SECRET_CODE_999"
    secret_name = "Иванов Иван Иванович"
    secret_phone = "+79991234567"

    def create_query():
        q = MagicMock()

        def exec_query():
            res = MagicMock()
            txt = q.Текст
            if "Справочник.БонусныеКарты" in txt and "Т.Код КАК Код" in txt:
                row1 = MagicMock()
                row1.Код = secret_barcode
                row1.Наименование = secret_name
                row1.РучнойКод = secret_code
                row1.Телефон = secret_phone
                row1.ЭтоГруппа = False
                row1.ПометкаУдаления = False
                row1.КартаЗапрещена = False

                sel = MagicMock()
                sel.Следующий.side_effect = [True, False]
                sel.Код = row1.Код
                sel.Наименование = row1.Наименование
                sel.РучнойКод = row1.РучнойКод
                sel.Телефон = row1.Телефон
                sel.ЭтоГруппа = row1.ЭтоГруппа
                sel.ПометкаУдаления = row1.ПометкаУдаления
                sel.КартаЗапрещена = row1.КартаЗапрещена
                res.Выбрать.return_value = sel
            elif "ВерсияДанных" in txt:
                sel = MagicMock()
                sel.Следующий.side_effect = [True, False]
                sel.Непустых = 1
                res.Выбрать.return_value = sel
            elif "РегистрНакопления.ОстаткиБонусныхКарт" in txt and "МинПериод" in txt:
                sel = MagicMock()
                sel.Следующий.side_effect = [True, False]
                sel.Всего = 10
                sel.Приход = 6
                sel.Расход = 4
                sel.МинПериод = "2024-01-01T12:00:00"
                sel.МаксПериод = "2024-05-01T12:00:00"
                res.Выбрать.return_value = sel
            elif "РегистраторЧек" in txt:
                sel = MagicMock()
                sel.Следующий.side_effect = [True, False]
                sel.РегистраторЧек = 8
                sel.РегистраторДвижениеБонусныхКарт = 2
                sel.Прочие = 0
                res.Выбрать.return_value = sel
            elif "КвоДублей" in txt or ("СГРУППИРОВАТЬ ПО" in txt and "НомерСтроки" in txt):
                sel = MagicMock()
                sel.Следующий.return_value = False
                res.Выбрать.return_value = sel
            elif "СДробнойЧастью" in txt:
                sel = MagicMock()
                sel.Следующий.side_effect = [True, False]
                sel.СДробнойЧастью = 0
                res.Выбрать.return_value = sel
            elif "ПустаяКарта" in txt:
                sel = MagicMock()
                sel.Следующий.side_effect = [True, False]
                sel.ПустаяКарта = 0
                res.Выбрать.return_value = sel
            elif "За30Дней" in txt:
                sel = MagicMock()
                sel.Следующий.side_effect = [True, False]
                sel.За30Дней = 3
                res.Выбрать.return_value = sel
            elif "ВсегоЧеков" in txt and "СоСкладом" in txt:
                sel = MagicMock()
                sel.Следующий.side_effect = [True, False]
                sel.ВсегоЧеков = 8
                sel.СоСкладом = 8
                sel.СНомером = 8
                res.Выбрать.return_value = sel
            elif "Остатки" in txt and "ОбщийОстаток" in txt:
                sel = MagicMock()
                sel.Следующий.side_effect = [True, False]
                sel.ВсегоКартСОстатком = 1
                sel.КартСОтрицательнымОстатком = 0
                sel.ОбщийОстаток = 500.0
                res.Выбрать.return_value = sel
            elif "ПродажиПоБонуснымКартам.Обороты" in txt:
                sel = MagicMock()
                sel.Следующий.side_effect = [True, False]
                sel.КартСОборотом = 1
                sel.ОбщийОборот = 1500.0
                res.Выбрать.return_value = sel
            elif "Документ.Чек" in txt and "СКартой" in txt:
                sel = MagicMock()
                sel.Следующий.side_effect = [True, False]
                sel.ВсегоЧеков = 20
                sel.СКартой = 5
                sel.СНачисленнымиБонусами = 4
                sel.СоСписаннымиБонусами = 1
                sel.СБонуснымиОперациями = 5
                res.Выбрать.return_value = sel
            elif "ТИПЗНАЧЕНИЯ(Т.Регистратор)" in txt:
                sel = MagicMock()
                mock_type1 = MagicMock()
                mock_type2 = MagicMock()
                sel.Следующий.side_effect = [True, True, False]
                type_prop = MagicMock()
                type_prop.side_effect = [mock_type1, mock_type2]
                type(sel).ТипРегистратора = property(lambda self: type_prop())
                kind_prop = MagicMock()
                kind_prop.side_effect = ["Приход", "Расход"]
                type(sel).ВидДвижения = property(lambda self: kind_prop())
                kvo_prop = MagicMock()
                kvo_prop.side_effect = [6, 4]
                type(sel).Кво = property(lambda self: kvo_prop())

                md1 = MagicMock()
                md1.FullName.return_value = "Документ.Чек"
                md2 = MagicMock()
                md2.FullName.return_value = "Документ.ОтчетКассовойСмены"
                mock_conn.Metadata.FindByType.side_effect = lambda t: md1 if t == mock_type1 else md2
                res.Выбрать.return_value = sel
            elif "Т.Регистратор ССЫЛКА Документ.ОтчетКассовойСмены" in txt and "КОЛИЧЕСТВО(*) КАК Всего" in txt:
                sel = MagicMock()
                sel.Следующий.side_effect = [True, False]
                sel.Всего = 4
                sel.СоСкладом = 4
                res.Выбрать.return_value = sel
            elif "Т.Регистратор ССЫЛКА Документ.ОтчетКассовойСмены" in txt and "Склад КАК Склад" in txt:
                sel = MagicMock()
                sel.Следующий.side_effect = [True, True, False]
                res.Выбрать.return_value = sel
            elif "Т.Регистратор ССЫЛКА Документ.ОтчетКассовойСмены" in txt and "POS КАК POS" in txt:
                sel = MagicMock()
                sel.Следующий.side_effect = [True, False]
                res.Выбрать.return_value = sel
            elif "ЗаписейСЧекомБольше0" in txt:
                sel = MagicMock()
                sel.Следующий.side_effect = [True, False]
                sel.ЗаписейСЧекомБольше0 = 5
                res.Выбрать.return_value = sel
            elif "КартСЧекомБольше0" in txt:
                sel = MagicMock()
                sel.Следующий.side_effect = [True, False]
                sel.КартСЧекомБольше0 = 1
                res.Выбрать.return_value = sel
            elif "КартСОстатком" in txt:
                sel = MagicMock()
                sel.Следующий.side_effect = [True, False]
                sel.КартСОстатком = 1
                res.Выбрать.return_value = sel
            elif "КвоДвижений" in txt and "ДвижениеБонусныхКарт" in txt:
                sel = MagicMock()
                sel.Следующий.side_effect = [True, False]
                sel.ДатаДня = "2024-05-01"
                sel.КвоДвижений = 4
                res.Выбрать.return_value = sel
            else:
                sel = MagicMock()
                sel.Следующий.return_value = False
                res.Выбрать.return_value = sel
            return res

        q.Выполнить.side_effect = exec_query
        return q

    mock_conn.NewObject.side_effect = lambda obj_type: create_query()

    profile = collect_data_profile(mock_conn)
    json_path, md_path = write_data_profile_reports(profile, tmp_path)

    json_text = json_path.read_text(encoding="utf-8")
    md_text = md_path.read_text(encoding="utf-8")

    # Strict privacy verification: zero raw customer strings leak to outputs
    assert secret_barcode not in json_text
    assert secret_barcode not in md_text
    assert secret_code not in json_text
    assert secret_code not in md_text
    assert secret_name not in json_text
    assert secret_name not in md_text
    assert secret_phone not in json_text
    assert secret_phone not in md_text
    assert "9991234567" not in json_text
    assert "9991234567" not in md_text
    assert "500.0" not in json_text
    assert "500.0" not in md_text
    assert "1500.0" not in json_text
    assert "1500.0" not in md_text

    # Aggregate assertions
    assert profile["bonus_cards"]["total_elements"] == 1
    assert profile["bonus_balances"]["total_balance_sign"] == "> 0"
    assert profile["bonus_sales_turnover"]["total_turnover_sign"] == "> 0"
    assert profile["bonus_movements"]["total_records"] == 10
    assert profile["checks"]["total_checks"] == 20

    # 7.1 assertions
    det = profile["bonus_movements"]["detailed_recorders"]
    assert "Документ.Чек" in det
    assert det["Документ.Чек"]["total"] == 6
    assert det["Документ.ОтчетКассовойСмены"]["total"] == 4

    # 7.2 assertions
    shift = profile["bonus_movements"]["shift_report_recorders"]
    assert shift["present_in_recorders"] is True
    assert shift["total_movements"] == 4
    assert shift["with_warehouse"] == 4
    assert shift["distinct_warehouses_count"] == 2
    assert shift["distinct_pos_count"] == 1

    # 7.3 assertions
    c_rel = profile["bonus_cards"]["code_phone_relation"]
    assert c_rel["total_cards"] == 1
    assert "zfill_13" in c_rel
    assert c_rel["zfill_13"]["unique_values_count"] == 1

    # 7.4 assertions
    spend = profile["bonus_movements"]["spend_total_realism"]
    assert spend["receipt_records_with_summa_cheka_gt_0"] == 5
    assert spend["cards_with_summa_cheka_gt_0"] == 1

    # 7.5 assertions
    n_freq = profile["bonus_cards"]["name_duplicates_analysis"]
    assert n_freq["most_frequent_count"] == 1
    assert n_freq["most_frequent_name_length"] == len(secret_name)

    # 7.6 assertions
    dyn = profile["monthly_dynamics"]
    assert len(dyn["balances_by_month_end"]) == 4
    assert dyn["balances_by_month_end"][0]["cards_with_non_zero_balance"] == 1
    assert dyn["peak_expense_day_movement_doc"]["expense_movements_count"] == 4


def test_profile_code_phone_relation_and_name_frequency() -> None:
    """profile_code_phone_relation (7.3) and profile_name_frequency (7.5) calculate aggregates without leaking raw strings."""
    from poscenter_loyalty_agent.stage0.data_profile import (
        profile_code_phone_relation,
        profile_name_frequency,
    )

    codes = [
        "79991234567",       # 11 digits, starts with 7, matches phone digits
        "+7 (999) 123-45-67", # digits match phone
        "00123",             # starts with '0'
        "123",               # short code
        "89990001122",       # 11 digits, starts with 8, matches phone last 10 digits
        "",                  # empty
    ]
    phones = [
        "+79991234567",      # identical digits to codes[0]
        "79991234567",       # identical digits to codes[1]
        "+70001112233",      # no match
        "",                  # empty phone
        "+79990001122",      # last 10 digits match codes[4]
        "+78889990011",      # empty code
    ]
    names = [
        "Иван Иванов",
        "Петр Петров",
        "Иван Иванов",
        "Иван Иванов",
        "Сидор Сидоров",
        "",
    ]

    # Test 7.3 Code-Phone relation
    rel = profile_code_phone_relation(codes, phones)
    assert rel["total_cards"] == 6
    assert rel["code_digits_equal_phone_digits_count"] == 2  # codes[0] and codes[1]
    assert rel["last_10_digits_match_count"] == 3           # codes[0], codes[1], codes[4]
    assert rel["code_11_digits_starts_7_or_8_count"] == 3   # codes[0], codes[1], and codes[4]
    assert rel["code_starts_with_zero_count"] == 1          # codes[2]

    zfill = rel["zfill_13"]
    assert zfill["non_empty_codes_padded"] == 5
    # "00123".zfill(13) == "0000000000123", "123".zfill(13) == "0000000000123" -> collision!
    assert zfill["duplicate_distinct_values"] == 1
    assert zfill["duplicate_total_rows"] == 2
    assert zfill["has_collisions"] is True

    # Test 7.5 Name duplicates
    freq = profile_name_frequency(names)
    assert freq["duplicate_distinct_names"] == 1  # "Иван Иванов" appears 3 times
    assert freq["duplicate_total_rows"] == 3
    assert freq["most_frequent_count"] == 3
    assert freq["most_frequent_name_length"] == len("Иван Иванов")


def test_profile_recorder_types_detailed_fallback() -> None:
    """When Method 1 (ТИПЗНАЧЕНИЯ) fails in 7.1, Method 2 (Т.Регистратор) fallback succeeds."""
    from poscenter_loyalty_agent.stage0.data_profile import profile_recorder_types_detailed

    mock_conn = MagicMock()
    mock_conn.String.side_effect = lambda x: f"Str({x})"

    doc_ref1 = MagicMock()
    doc_ref2 = MagicMock()

    type1 = MagicMock()
    type2 = MagicMock()

    md1 = MagicMock()
    md1.FullName.return_value = "Документ.Чек"
    md2 = MagicMock()
    md2.FullName.return_value = "Документ.ОтчетКассовойСмены"

    mock_conn.TypeOf.side_effect = lambda ref: type1 if ref == doc_ref1 else type2
    mock_conn.Metadata.FindByType.side_effect = lambda t: md1 if t == type1 else md2

    q1 = MagicMock()
    q1.Выполнить.side_effect = RuntimeError("Grouping by ТИПЗНАЧЕНИЯ not supported on platform")

    q2 = MagicMock()
    res2 = MagicMock()
    sel2 = MagicMock()
    sel2.Следующий.side_effect = [True, True, False]

    ref_prop = MagicMock()
    ref_prop.side_effect = [doc_ref1, doc_ref2]
    type(sel2).Регистратор = property(lambda self: ref_prop())

    kind_prop = MagicMock()
    kind_prop.side_effect = ["Приход", "Расход"]
    type(sel2).ВидДвижения = property(lambda self: kind_prop())

    kvo_prop = MagicMock()
    kvo_prop.side_effect = [10, 5]
    type(sel2).Кво = property(lambda self: kvo_prop())

    res2.Выбрать.return_value = sel2
    q2.Выполнить.return_value = res2

    mock_conn.NewObject.side_effect = [q1, q2]

    breakdown = profile_recorder_types_detailed(mock_conn)
    assert "Документ.Чек" in breakdown
    assert breakdown["Документ.Чек"]["total"] == 10
    assert breakdown["Документ.Чек"]["receipt"] == 10
    assert "Документ.ОтчетКассовойСмены" in breakdown
    assert breakdown["Документ.ОтчетКассовойСмены"]["total"] == 5
    assert breakdown["Документ.ОтчетКассовойСмены"]["expense"] == 5


def test_profile_monthly_dynamics_fallback() -> None:
    """When virtual table fails in 7.6, movement query fallback computes active card counts."""
    from poscenter_loyalty_agent.stage0.data_profile import profile_monthly_balances_and_dynamics

    mock_conn = MagicMock()

    def create_mock_query():
        q = MagicMock()

        def run_q():
            if "Остатки(&Период" in q.Текст:
                raise RuntimeError("Virtual table unavailable")
            if "Т.Период <= &Период" in q.Текст:
                res = MagicMock()
                sel = MagicMock()
                sel.Следующий.side_effect = [True, True, False]  # 2 active cards
                res.Выбрать.return_value = sel
                return res
            if "КвоДвижений" in q.Текст:
                res = MagicMock()
                sel = MagicMock()
                sel.Следующий.side_effect = [True, False]
                sel.ДатаДня = "2024-05-15 00:00:00"
                sel.КвоДвижений = 7
                res.Выбрать.return_value = sel
                return res
            res = MagicMock()
            sel = MagicMock()
            sel.Следующий.return_value = False
            res.Выбрать.return_value = sel
            return res

        q.Выполнить.side_effect = run_q
        return q

    mock_conn.NewObject.side_effect = lambda _: create_mock_query()

    dyn = profile_monthly_balances_and_dynamics(mock_conn)
    assert len(dyn["balances_by_month_end"]) == 4
    for entry in dyn["balances_by_month_end"]:
        assert entry["cards_with_non_zero_balance"] == 2
        assert entry["calculation_method"] == "movements_fallback"
    assert dyn["peak_expense_day_movement_doc"]["peak_date"] == "2024-05-15"
    assert dyn["peak_expense_day_movement_doc"]["expense_movements_count"] == 7







