"""CLI subcommands for Stage 0 Discovery Toolkit."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from poscenter_loyalty_agent.config import get_settings
from poscenter_loyalty_agent.stage0.environment import check_environment
from poscenter_loyalty_agent.stage0.metadata_probe import ComMetadataProvider, FakeMetadataProvider
from poscenter_loyalty_agent.stage0.report import (
    write_discovery_summary_report,
    write_environment_report,
    write_inventory_reports,
)
from poscenter_loyalty_agent.stage0.validator import validate_mapping


def cmd_check_environment(args: argparse.Namespace) -> int:
    """Run stage0 check-environment command."""
    settings = get_settings()
    env_result = check_environment(settings)
    print(env_result.format_console())

    output_dir = Path(getattr(args, "output_dir", "stage0_output"))
    write_environment_report(env_result, output_dir)
    print(f"\nEnvironment report saved to: {output_dir / 'environment.json'}")
    return 0


def cmd_probe_metadata(args: argparse.Namespace) -> int:
    """Run stage0 probe-metadata command."""
    settings = get_settings()
    env_result = check_environment(settings)
    output_dir = Path(getattr(args, "output_dir", "stage0_output"))
    output_dir.mkdir(parents=True, exist_ok=True)

    # Always save environment check first
    write_environment_report(env_result, output_dir)

    use_fake = getattr(args, "use_fake_provider", False)

    if not env_result.is_windows and not use_fake:
        print(env_result.format_console())
        print(
            "\nNOTICE: Real 1C COM metadata probing requires a Windows host with V83.COMConnector.",
            file=sys.stderr,
        )
        print(
            "Phase A Discovery Toolkit is ready. Phase B Real Pilot Execution is blocked by host environment.",
            file=sys.stderr,
        )
        write_discovery_summary_report(env_result, inventory=None, output_dir=output_dir)
        return 1

    if not env_result.connection_string_configured and not use_fake:
        print("ERROR: ONE_CONNECTION_STRING is not configured in settings.", file=sys.stderr)
        return 1

    print("Probing POSCENTER ONE metadata...")
    provider = FakeMetadataProvider() if use_fake else ComMetadataProvider(settings.one_connection_string)

    try:
        inventory = provider.discover_metadata()
        json_path, md_path = write_inventory_reports(inventory, output_dir)
        report_path = write_discovery_summary_report(env_result, inventory, output_dir)

        print("=== Metadata Probe Completed Successfully ===")
        print(f"Total Discovered Objects:       {len(inventory.objects)}")
        print(f"Candidate Loyalty Cards:        {len(inventory.candidate_cards)}")
        print(f"Candidate Balance Registers:    {len(inventory.candidate_registers)}")
        print(f"Candidate Transactions:         {len(inventory.candidate_transactions)}")
        print(f"Inventory JSON:                 {json_path}")
        print(f"Inventory Markdown:             {md_path}")
        print(f"Discovery Summary Report:       {report_path}")
        return 0
    except Exception as exc:
        print(f"ERROR: Metadata probing failed: {exc}", file=sys.stderr)
        return 1


def cmd_validate_mapping(args: argparse.Namespace) -> int:
    """Run stage0 validate-mapping command."""
    mapping_file = Path(args.mapping_file)
    report = validate_mapping(mapping_file)
    print(report.format_console())
    return 0 if report.is_valid else 1


def register_stage0_subparsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register stage0 subcommand tree under agent main CLI."""
    p_stage0 = subparsers.add_parser(
        "stage0",
        help="Stage 0 Discovery Toolkit for real POSCENTER ONE mapping",
        description="Stage 0 Discovery and Mapping verification tools for POSCENTER ONE",
    )
    stage0_subparsers = p_stage0.add_subparsers(dest="stage0_command", required=True)

    # stage0 check-environment
    p_env = stage0_subparsers.add_parser(
        "check-environment",
        help="Verify host OS, pywin32, and V83.COMConnector readiness",
    )
    p_env.add_argument(
        "--output-dir",
        default="stage0_output",
        help="Directory to store environment.json (default: stage0_output)",
    )
    p_env.set_defaults(func=cmd_check_environment)

    # stage0 probe-metadata
    p_probe = stage0_subparsers.add_parser(
        "probe-metadata",
        help="Extract technical 1C metadata inventory (strictly read-only)",
    )
    p_probe.add_argument(
        "--output-dir",
        default="stage0_output",
        help="Directory to store metadata inventory artifacts (default: stage0_output)",
    )
    p_probe.add_argument(
        "--use-fake-provider",
        action="store_true",
        help="Internal flag for testing discovery serialization on non-Windows hosts",
    )
    p_probe.set_defaults(func=cmd_probe_metadata)

    # stage0 validate-mapping
    p_val = stage0_subparsers.add_parser(
        "validate-mapping",
        help="Validate a Stage 0 mapping artifact against schema, placeholders, and PII",
    )
    p_val.add_argument(
        "mapping_file",
        help="Path to stage0_mapping.json to validate",
    )
    p_val.set_defaults(func=cmd_validate_mapping)
