"""CLI subcommands for Stage 0 Discovery Toolkit."""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

from poscenter_loyalty_agent.config import get_settings
from poscenter_loyalty_agent.one_com import sanitize_connection_string
from poscenter_loyalty_agent.stage0.environment import (
    FLAG_NOT_VERIFIED,
    FLAG_VERIFIED,
    VerificationFlags,
    check_environment,
)
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
    env_result.release_connection()
    return 0


def cmd_probe_metadata(args: argparse.Namespace) -> int:
    """Run stage0 probe-metadata command."""
    settings = get_settings()
    output_dir = Path(getattr(args, "output_dir", "stage0_output"))
    use_fake = getattr(args, "use_fake_provider", False)

    # Fake provider isolation: allowed ONLY when AGENT_ENV == 'test'
    if use_fake:
        if settings.agent_env != "test":
            print(
                f"ERROR: --use-fake-provider is strictly restricted to AGENT_ENV='test' "
                f"(current: '{settings.agent_env}'). "
                "Fake metadata provider cannot be used in development or production environments.",
                file=sys.stderr,
            )
            return 1
        env_result = check_environment(settings.model_copy(update={"one_connection_string": ""}))
        env_result.verification_flags = VerificationFlags()
        env_result.details.append("Fake metadata provider run: REAL_* verification flags forced to NOT VERIFIED.")
    else:
        env_result = check_environment(settings)

    output_dir.mkdir(parents=True, exist_ok=True)
    # Always save initial environment check first
    write_environment_report(env_result, output_dir)

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

    print("Probing POSCENTER ONE metadata...", flush=True)
    provider = (
        FakeMetadataProvider()
        if use_fake
        else ComMetadataProvider(settings.one_connection_string, existing_connection=env_result.active_connection)
    )

    try:
        inventory = provider.discover_metadata()

        # 1. Validate safety & write inventory first
        print("Writing inventory reports...", flush=True)
        json_path, md_path = write_inventory_reports(inventory, output_dir)
        print("Inventory reports written successfully.", flush=True)

        # 2. ONLY AFTER successful real inventory generation and safety validation:
        if not use_fake and env_result.is_windows:
            env_result.verification_flags.real_one_metadata_discovery = FLAG_VERIFIED
            env_result.details.append("Real 1C metadata inventory successfully extracted and verified.")

        # 3. Synchronize both final environment.json and STAGE0_DISCOVERY_REPORT.md
        print("Writing final environment and summary reports...", flush=True)
        write_environment_report(env_result, output_dir)
        report_path = write_discovery_summary_report(env_result, inventory, output_dir)
        print("Summary report written successfully.", flush=True)

        print("=== Metadata Probe Completed Successfully ===", flush=True)
        print(f"Total Discovered Objects:       {len(inventory.objects)}", flush=True)
        print(f"Candidate Loyalty Cards:        {len(inventory.candidate_cards)}", flush=True)
        print(f"Candidate Balance Sources:      {len(inventory.candidate_balance_sources)}", flush=True)
        print(f"Candidate Transactions:         {len(inventory.candidate_transactions)}", flush=True)
        print(f"Inventory JSON:                 {json_path}", flush=True)
        print(f"Inventory Markdown:             {md_path}", flush=True)
        print(f"Discovery Summary Report:       {report_path}", flush=True)
        return 0
    except Exception as exc:
        safe_tb = sanitize_connection_string(traceback.format_exc())
        msg = f"ERROR: Metadata probing failed: {exc}\n{safe_tb}"
        print(msg, flush=True)
        print(msg, file=sys.stderr, flush=True)
        # In failure mode, ensure metadata discovery remains NOT VERIFIED in all artifacts
        env_result.verification_flags.real_one_metadata_discovery = FLAG_NOT_VERIFIED
        try:
            write_environment_report(env_result, output_dir)
            write_discovery_summary_report(env_result, None, output_dir)
        except Exception as report_err:
            print(f"ERROR: Fallback report generation failed: {report_err}", file=sys.stderr, flush=True)
        return 1
    finally:
        env_result.release_connection()


def cmd_validate_mapping(args: argparse.Namespace) -> int:
    """Run stage0 validate-mapping command."""
    mapping_file = Path(args.mapping_file)
    require_verified = getattr(args, "require_verified", False)
    report = validate_mapping(mapping_file, require_verified=require_verified)
    print(report.format_console())
    return 0 if report.is_valid else 1


def cmd_profile_data(args: argparse.Namespace) -> int:
    """Run stage0 profile-data command."""
    settings = get_settings()
    output_dir = Path(getattr(args, "output_dir", "stage0_output"))
    use_fake = getattr(args, "use_fake_provider", False)

    if use_fake:
        if settings.agent_env != "test":
            print(
                f"ERROR: --use-fake-provider is strictly restricted to AGENT_ENV='test' "
                f"(current: '{settings.agent_env}').",
                file=sys.stderr,
            )
            return 1
        env_result = check_environment(settings.model_copy(update={"one_connection_string": ""}))
        env_result.verification_flags = VerificationFlags()
    else:
        env_result = check_environment(settings)

    output_dir.mkdir(parents=True, exist_ok=True)

    if not env_result.is_windows and not use_fake:
        print(env_result.format_console())
        print("ERROR: Real 1C COM data profiling requires Windows with V83.COMConnector.", file=sys.stderr)
        return 1

    if not env_result.connection_string_configured and not use_fake:
        print("ERROR: ONE_CONNECTION_STRING is not configured in settings.", file=sys.stderr)
        return 1

    print("Profiling POSCENTER ONE data...", flush=True)

    try:
        if use_fake:
            from datetime import UTC, datetime

            from poscenter_loyalty_agent.stage0.data_profile import (
                CATALOG_BONUS_CARDS,
                DOCUMENT_CHECK,
                compute_length_stats,
                write_data_profile_reports,
            )

            profile = {
                "collected_at": datetime.now(UTC).isoformat(),
                "bonus_cards": {
                    "object_name": CATALOG_BONUS_CARDS,
                    "total_elements": 100,
                    "is_group_count": 5,
                    "deletion_mark_count": 2,
                    "card_disabled_count": 3,
                    "code_profile": {
                        "empty": 0,
                        "only_digits": 100,
                        "exactly_13_digits": 90,
                        "valid_ean13": 85,
                        "duplicate_distinct_values": 0,
                        "duplicate_total_rows": 0,
                        "name_like_has_letters": 0,
                        "length_distribution": compute_length_stats([13] * 90 + [10] * 10),
                    },
                    "name_profile": {
                        "empty": 0,
                        "only_digits": 0,
                        "exactly_13_digits": 0,
                        "valid_ean13": 0,
                        "duplicate_distinct_values": 0,
                        "duplicate_total_rows": 0,
                        "name_like_has_letters": 100,
                        "length_distribution": compute_length_stats([20] * 100),
                    },
                    "manual_code_profile": {
                        "empty": 50,
                        "only_digits": 50,
                        "exactly_13_digits": 50,
                        "valid_ean13": 50,
                        "duplicate_distinct_values": 0,
                        "duplicate_total_rows": 0,
                        "name_like_has_letters": 0,
                        "length_distribution": compute_length_stats([13] * 50),
                    },
                    "phone_profile": {
                        "empty": 10,
                        "normalizable": 80,
                        "other": 10,
                        "digit_length_distribution": compute_length_stats([11] * 80 + [7] * 10),
                    },
                    "code_phone_relation": {
                        "total_cards": 100,
                        "code_digits_equal_phone_digits_count": 0,
                        "code_digits_equal_phone_digits_percent": 0.0,
                        "last_10_digits_match_count": 0,
                        "last_10_digits_match_percent": 0.0,
                        "code_11_digits_starts_7_or_8_count": 0,
                        "code_11_digits_starts_7_or_8_percent": 0.0,
                        "code_starts_with_zero_count": 0,
                        "code_starts_with_zero_percent": 0.0,
                        "zfill_13": {
                            "non_empty_codes_padded": 100,
                            "unique_values_count": 100,
                            "duplicate_distinct_values": 0,
                            "duplicate_total_rows": 0,
                            "has_collisions": False,
                        },
                    },
                    "name_duplicates_analysis": {
                        "duplicate_distinct_names": 0,
                        "duplicate_total_rows": 0,
                        "most_frequent_count": 1,
                        "most_frequent_name_length": 20,
                    },
                    "data_version": {"status": "available", "non_empty_count": 95},
                },
                "bonus_movements": {
                    "total_records": 500,
                    "receipt_count": 300,
                    "expense_count": 200,
                    "min_period": "2024-01-01T10:00:00",
                    "max_period": "2024-06-01T15:00:00",
                    "records_last_30_days": 50,
                    "empty_bonus_card_count": 0,
                    "recorder_line_number_duplicates": 0,
                    "recorders": {"document_check": 450, "document_bonus_card_movement": 50, "other": 0},
                    "detailed_recorders": {
                        "Документ.Чек": {"total": 450, "receipt": 300, "expense": 150},
                        "Документ.ДвижениеБонусныхКарт": {"total": 50, "receipt": 0, "expense": 50},
                    },
                    "shift_report_recorders": {
                        "present_in_recorders": False,
                        "total_movements": 0,
                        "with_warehouse": 0,
                        "warehouse_share_percent": 0.0,
                        "distinct_warehouses_count": 0,
                        "distinct_pos_count": 0,
                    },
                    "spend_total_realism": {
                        "receipt_records_with_summa_cheka_gt_0": 300,
                        "receipt_records_total": 300,
                        "receipt_records_share_percent": 100.0,
                        "cards_with_summa_cheka_gt_0": 80,
                        "cards_total": 100,
                        "cards_share_percent": 80.0,
                    },
                    "sum_breakdown_by_kind": {
                        "Приход": {"less_than_zero": 0, "equal_zero": 0, "greater_than_zero": 300},
                        "Расход": {"less_than_zero": 0, "equal_zero": 0, "greater_than_zero": 200},
                    },
                    "has_fractional_points": False,
                    "fractional_records_count": 0,
                    "max_decimal_places": 0,
                    "check_recorders": {
                        "total_movements_from_checks": 450,
                        "with_non_empty_warehouse": 450,
                        "with_non_empty_number": 450,
                        "warehouse_coverage_percent": 100.0,
                        "number_coverage_percent": 100.0,
                    },
                },
                "bonus_balances": {
                    "cards_with_non_zero_balance": 80,
                    "cards_with_negative_balance": 0,
                    "total_balance_sign": "> 0",
                },
                "bonus_sales_turnover": {
                    "cards_with_turnover": 75,
                    "total_turnover_sign": "> 0",
                },
                "checks": {
                    "object_name": DOCUMENT_CHECK,
                    "total_checks": 1000,
                    "checks_with_card": 400,
                    "checks_with_accrued_bonuses": 300,
                    "checks_with_spent_bonuses": 100,
                    "checks_with_any_bonus_operation": 350,
                    "card_coverage_percent": 40.0,
                    "bonus_operation_percent": 35.0,
                },
                "monthly_dynamics": {
                    "balances_by_month_end": [
                        {
                            "date": "2026-07-31 23:59:59",
                            "cards_with_non_zero_balance": 70,
                            "calculation_method": "virtual_table",
                        },
                        {
                            "date": "2026-08-31 23:59:59",
                            "cards_with_non_zero_balance": 75,
                            "calculation_method": "virtual_table",
                        },
                        {
                            "date": "2026-09-30 23:59:59",
                            "cards_with_non_zero_balance": 78,
                            "calculation_method": "virtual_table",
                        },
                        {
                            "date": "2026-10-31 23:59:59",
                            "cards_with_non_zero_balance": 80,
                            "calculation_method": "virtual_table",
                        },
                    ],
                    "peak_expense_day_movement_doc": {
                        "document_type": "Документ.ДвижениеБонусныхКарт",
                        "peak_date": "2024-05-01",
                        "expense_movements_count": 10,
                    },
                },
                "conclusions_for_tor": [
                    "Первичный идентификатор карты: 'Код' уникален (0 дубликатов, 0 пустых) и рекомендуется как первичный ключ.",
                    "Чистка дубликатов: НЕ ТРЕБУЕТСЯ — все коды карт уникальны.",
                    "Дробные баллы: НЕ ОБНАРУЖЕНЫ — все суммы начислений и списаний строго целочисленные.",
                    "Аномалии в остатках: НЕ ОБНАРУЖЕНЫ — отрицательные балансы отсутствуют.",
                ],
            }
        else:
            conn = env_result.active_connection
            if conn is None:
                from poscenter_loyalty_agent.one_com import OneComConnector
                connector = OneComConnector(settings.one_connection_string)
                conn = connector.connect()
            from poscenter_loyalty_agent.stage0.data_profile import (
                collect_data_profile,
                write_data_profile_reports,
            )
            profile = collect_data_profile(conn)

        json_path, md_path = write_data_profile_reports(profile, output_dir)
        print("=== Data Profile Completed Successfully ===", flush=True)
        print(f"Data Profile JSON:     {json_path}", flush=True)
        print(f"Data Profile Markdown: {md_path}", flush=True)
        return 0
    except Exception as exc:
        safe_tb = sanitize_connection_string(traceback.format_exc())
        msg = f"ERROR: Data profiling failed: {exc}\n{safe_tb}"
        print(msg, flush=True)
        print(msg, file=sys.stderr, flush=True)
        return 1
    finally:
        env_result.release_connection()


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
        help="Test-only seam for validating serialization on non-Windows hosts (AGENT_ENV=test required)",
    )
    p_probe.set_defaults(func=cmd_probe_metadata)

    # stage0 profile-data
    p_profile = stage0_subparsers.add_parser(
        "profile-data",
        help="Extract data profile for loyalty objects (strictly read-only)",
    )
    p_profile.add_argument(
        "--output-dir",
        default="stage0_output",
        help="Directory to store data profile artifacts (default: stage0_output)",
    )
    p_profile.add_argument(
        "--use-fake-provider",
        action="store_true",
        help="Test-only seam for validating data profile on non-Windows hosts or mocks",
    )
    p_profile.set_defaults(func=cmd_profile_data)

    # stage0 validate-mapping
    p_val = stage0_subparsers.add_parser(
        "validate-mapping",
        help="Validate a Stage 0 mapping artifact against schema, placeholders, and PII",
    )
    p_val.add_argument(
        "mapping_file",
        help="Path to stage0_mapping.json to validate",
    )
    p_val.add_argument(
        "--require-verified",
        action="store_true",
        help="Enforce that artifact_kind is real_discovery and all mandatory P0 fields are VERIFIED",
    )
    p_val.set_defaults(func=cmd_validate_mapping)
