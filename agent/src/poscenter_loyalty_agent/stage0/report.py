"""Report generator for Stage 0 Discovery artifacts.

Produces sanitized markdown and JSON reports adhering strictly to safety standards.
Guarantees zero customer PII, zero connection strings, and zero raw barcode values.
"""

from __future__ import annotations

import json
from pathlib import Path

from poscenter_loyalty_agent.stage0.environment import EnvironmentCheckResult
from poscenter_loyalty_agent.stage0.metadata_probe import TargetedMetadataInventory
from poscenter_loyalty_agent.stage0.sanitizer import validate_safe_output


def write_environment_report(env_result: EnvironmentCheckResult, output_dir: Path) -> Path:
    """Save environment inspection result as sanitized JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)
    target_file = output_dir / "environment.json"

    data = env_result.model_dump()
    content = json.dumps(data, indent=2, ensure_ascii=False)
    validate_safe_output(content, context="environment.json")

    target_file.write_text(content, encoding="utf-8")
    return target_file


def write_inventory_reports(inventory: TargetedMetadataInventory, output_dir: Path) -> tuple[Path, Path]:
    """Save metadata inventory as sanitized JSON and Markdown with truthful coverage declarations."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "metadata_inventory.json"
    md_path = output_dir / "metadata_inventory.md"

    # JSON export
    data = inventory.model_dump()
    json_content = json.dumps(data, indent=2, ensure_ascii=False)
    validate_safe_output(json_content, context="metadata_inventory.json")
    json_path.write_text(json_content, encoding="utf-8")

    # Markdown export
    lines = [
        "# POSCENTER ONE Targeted Metadata Inventory",
        "",
        "> **Coverage Scope Notice:** " + inventory.coverage_limitation,
        "",
        f"- **Configuration:** `{inventory.configuration.configuration_name}`",
        f"- **Version:** `{inventory.configuration.configuration_version}`",
        f"- **Platform Major:** `{inventory.configuration.platform_major}`",
        f"- **Platform Version:** `{inventory.configuration.platform_version}` ({inventory.configuration.platform_version_state})",
        f"- **Discovered At:** `{inventory.discovered_at}`",
        f"- **Probed Categories ({len(inventory.probed_categories)}):** {', '.join(f'`{c}`' for c in inventory.probed_categories)}",
        f"- **Unprobed Categories ({len(inventory.unprobed_categories)}):** {', '.join(f'`{c}`' for c in inventory.unprobed_categories)}",
        f"- **Total Discovered Objects in Scope:** {len(inventory.objects)}",
        "",
        "## Candidate Objects (Heuristic Discovery)",
        "",
        "### Candidate Loyalty Cards",
    ]
    if inventory.candidate_cards:
        for c in inventory.candidate_cards:
            lines.append(f"- **`{c.object_name}`** ({c.category})")
            lines.append(f"  - *Reason:* {c.confidence_reason}")
            lines.append(f"  - *Requires Manual Verification:* {c.requires_manual_verification}")
    else:
        lines.append("*(No candidate card objects identified)*")

    lines.append("")
    lines.append("### Candidate Balance Sources")
    if inventory.candidate_balance_sources:
        for r in inventory.candidate_balance_sources:
            lines.append(f"- **`{r.object_name}`** ({r.category})")
            lines.append(f"  - *Reason:* {r.confidence_reason}")
            lines.append(f"  - *Requires Manual Verification:* {r.requires_manual_verification}")
    else:
        lines.append("*(No candidate balance sources identified)*")

    lines.append("")
    lines.append("### Candidate Transaction Sources")
    if inventory.candidate_transactions:
        for t in inventory.candidate_transactions:
            lines.append(f"- **`{t.object_name}`** ({t.category})")
            lines.append(f"  - *Reason:* {t.confidence_reason}")
            lines.append(f"  - *Requires Manual Verification:* {t.requires_manual_verification}")
    else:
        lines.append("*(No candidate transaction sources identified)*")

    lines.append("")
    lines.append("## Detailed Metadata Objects")
    lines.append("")
    for obj in inventory.objects:
        syn = f" ({obj.synonym})" if obj.synonym else ""
        lines.append(f"### `{obj.category}.{obj.name}`{syn}")
        if obj.fields:
            lines.append("| Field Name | Synonym | Type | Kind |")
            lines.append("|---|---|---|---|")
            for f in obj.fields:
                kind = "Dimension" if f.is_dimension else ("Resource" if f.is_resource else "Attribute")
                f_syn = f.synonym or "-"
                lines.append(f"| `{f.name}` | {f_syn} | `{f.type_desc}` | {kind} |")
        if obj.tabular_sections:
            lines.append(f"**Tabular Sections:** {', '.join(f'`{t}`' for t in obj.tabular_sections)}")
        lines.append("")

    md_content = "\n".join(lines)
    validate_safe_output(md_content, context="metadata_inventory.md")
    md_path.write_text(md_content, encoding="utf-8")

    return json_path, md_path


def write_discovery_summary_report(
    env_result: EnvironmentCheckResult,
    inventory: TargetedMetadataInventory | None,
    output_dir: Path,
) -> Path:
    """Generate canonical STAGE0_DISCOVERY_REPORT.md conforming to Section 38."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "STAGE0_DISCOVERY_REPORT.md"

    conf_name = inventory.configuration.configuration_name if inventory else "NOT DISCOVERED"
    conf_ver = inventory.configuration.configuration_version if inventory else "NOT DISCOVERED"
    plat_major = inventory.configuration.platform_major if inventory else "8.3"
    plat_ver = inventory.configuration.platform_version if inventory else "NOT_AVAILABLE"
    plat_ver_state = inventory.configuration.platform_version_state if inventory else "NOT_STARTED"

    lines = [
        "# Stage 0 Discovery Report — POSCENTER ONE",
        "",
        "## Environment",
        f"- Operating System: `{env_result.platform}`",
        f"- Windows Environment: `{env_result.is_windows}`",
        f"- pywin32 Available: `{env_result.pywin32_available}`",
        f"- V83.COMConnector Available: `{env_result.com_connector_available}`",
        f"- Connection String Configured: `{env_result.connection_string_configured}`",
        "",
        "## COM Verification",
        f"- REAL_WINDOWS_SERVICE: `{env_result.verification_flags.real_windows_service}`",
        f"- REAL_V83_COMCONNECTOR: `{env_result.verification_flags.real_v83_comconnector}`",
        f"- REAL_ONE_CONNECTION: `{env_result.verification_flags.real_one_connection}`",
        f"- REAL_ONE_METADATA_DISCOVERY: `{env_result.verification_flags.real_one_metadata_discovery}`",
        f"- REAL_ONE_MAPPING: `{env_result.verification_flags.real_one_mapping}`",
        "",
        "## Configuration Identity",
        f"- Configuration Name: `{conf_name}`",
        f"- Configuration Version: `{conf_ver}`",
        f"- Platform Major: `{plat_major}`",
        f"- Exact Platform Version: `{plat_ver}` ({plat_ver_state})",
        "",
        "## Metadata Inventory",
    ]

    if inventory:
        lines.append(f"- Scope: `{inventory.coverage_scope}` ({inventory.coverage_limitation})")
        lines.append(f"- Discovered Objects Count: {len(inventory.objects)}")
        lines.append(f"- Candidate Cards Identified: {len(inventory.candidate_cards)}")
        lines.append(f"- Candidate Balance Sources Identified: {len(inventory.candidate_balance_sources)}")
        lines.append(f"- Candidate Transactions Identified: {len(inventory.candidate_transactions)}")
    else:
        lines.append("- Metadata discovery skipped (real 1C environment not connected).")

    sections = [
        ("Card Source", "NOT VERIFIED: Requires real pilot POSCENTER ONE infobase execution."),
        ("Barcode", "NOT VERIFIED: Requires aggregate proof of the 13-digit loyalty-card barcode field."),
        ("Phone", "NOT VERIFIED: Requires aggregate proof of customer mobile phone field."),
        ("Customer Name", "NOT VERIFIED: Requires inspection of customer full name field."),
        ("Balance", "NOT VERIFIED: Requires identification and verification of the actual balance source."),
        ("Blocked State", "NOT VERIFIED: Requires identification of the actual source or rule for card availability/block status."),
        ("Updated Timestamp", "NOT VERIFIED: Requires identification of verified source or deterministic versioning rule for update semantics."),
        ("Transaction Source", "NOT VERIFIED: Requires identification of the actual loyalty movement source."),
        ("Stable External ID", "NOT VERIFIED: Requires single immutable identifier or verified deterministic composite identity."),
        ("Transaction Type", "NOT VERIFIED: Requires verification of source movement semantics and their deterministic mapping to the Cloud type string."),
        ("Balance After", "NOT VERIFIED: Requires verification if stored or derivable."),
        ("Receipt", "NOT VERIFIED: Requires verification whether a safe source for Cloud receipt_ref exists without PII."),
        ("Store", "NOT VERIFIED: Requires verification whether a reliable source for the Cloud store field exists."),
        ("Incremental Cursor", "NOT VERIFIED: Requires deterministic ordering fields and tie-breaker."),
        ("PII Review", "PASS: Zero customer PII, zero credentials, zero passwords present in discovery output."),
        ("Open Questions", "Awaiting Phase B execution on Windows host with live pilot POSCENTER ONE."),
        (
            "Mapping Status",
            (
                "READY_FOR_REAL_ONE_DISCOVERY (Phase A Discovery Toolkit complete; "
                "Phase B blocked by environment requirements)."
            ),
        ),
    ]

    for title, desc in sections:
        lines.append("")
        lines.append(f"## {title}")
        lines.append(desc)

    content = "\n".join(lines)
    validate_safe_output(content, context="STAGE0_DISCOVERY_REPORT.md")
    report_path.write_text(content, encoding="utf-8")
    return report_path


def write_final_discovery_artifacts(
    env_result: EnvironmentCheckResult,
    inventory: TargetedMetadataInventory,
    output_dir: Path,
) -> tuple[Path, Path, Path, Path]:
    """Write inventory reports, final synchronized environment.json, and summary report.

    Guarantees:
    - Inventory is validated for safety and written first.
    - environment.json and STAGE0_DISCOVERY_REPORT.md both use the exact same final env_result.
    """
    json_path, md_path = write_inventory_reports(inventory, output_dir)
    env_path = write_environment_report(env_result, output_dir)
    summary_path = write_discovery_summary_report(env_result, inventory, output_dir)
    return json_path, md_path, env_path, summary_path

