"""Command line interface (CLI) for POSCENTER Loyalty Agent."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from poscenter_loyalty_agent.config import get_settings
from poscenter_loyalty_agent.logging import configure_logging
from poscenter_loyalty_agent.runtime import AgentRuntime
from poscenter_loyalty_agent.state_store import StateStore
from poscenter_loyalty_agent.windows_service import handle_service_command

logger = logging.getLogger(__name__)


def cmd_run(args: argparse.Namespace) -> int:
    """Run the agent in foreground console mode or execute standalone dry-run."""
    settings = get_settings()
    if getattr(args, "dry_run", False) or settings.dry_run:
        from poscenter_loyalty_agent.dry_run import run_dry_run_cli

        return run_dry_run_cli(settings)
    configure_logging(
        log_level=settings.log_level,
        log_file_path=settings.log_file_path,
        max_bytes=settings.log_max_bytes,
        backup_count=settings.log_backup_count,
    )
    runtime = AgentRuntime(settings=settings)
    try:
        asyncio.run(runtime.run())
        return 0
    except KeyboardInterrupt:
        logger.info("Agent stopped by user interrupt.")
        return 0
    except Exception as exc:
        logger.exception("Agent stopped due to fatal error: %s", exc)
        return 1


def cmd_check_config(args: argparse.Namespace) -> int:
    """Validate settings, credentials, and state store."""
    try:
        settings = get_settings()
        configure_logging(log_level="INFO")
        print("=== POSCENTER Loyalty Agent Configuration Check ===")
        print(f"Agent Version:          {settings.agent_version}")
        print(f"Environment:            {settings.agent_env}")
        print(f"Cloud API Base URL:     {settings.cloud_api_base_url}")
        print(f"Cloud API Key:          {'*' * 8}... (configured)")
        print(f"Sync Interval:          {settings.sync_interval_seconds}s")
        print(f"Heartbeat Interval:     {settings.heartbeat_interval_seconds}s")
        print(f"Adapter Mode:           {settings.one_adapter_mode}")
        print(f"State DB Path:          {settings.state_db_path}")
        print(f"Lock File Path:         {settings.lock_file_path}")
        print(f"Log File Path:          {settings.log_file_path}")
        print(f"Log Rotation Max Bytes: {settings.log_max_bytes}")
        print(f"Log Backup Count:       {settings.log_backup_count}")

        # Check DB connectivity
        store = StateStore(settings.state_db_path)
        status = store.get_status()
        print(f"State Store Status:   OK (SQLite ready, last sync: {status.last_successful_sync_at or 'none'})")

        if settings.one_adapter_mode == "stub":
            print("\nNOTICE: ONE_ADAPTER_MODE is 'stub'. Real POSCENTER ONE sync requires Stage 0 discovery.")
            print("        See docs/ONE_STAGE0_REQUIRED.md for instructions.")

        print("\nAll configuration and state checks passed successfully.")
        return 0
    except Exception as exc:
        print(f"ERROR: Configuration check failed: {exc}", file=sys.stderr)
        return 1


def cmd_status(args: argparse.Namespace) -> int:
    """Display current agent operational status and checkpoint positions."""
    try:
        settings = get_settings()
        store = StateStore(settings.state_db_path)
        status = store.get_status()

        cards_status = "set" if status.cards_committed_cursor else "(none)"
        tx_status = "set" if status.transactions_committed_cursor else "(none)"
        print("=== POSCENTER Loyalty Agent Operational Status ===")
        print(f"State DB Path:                 {settings.state_db_path}")
        print(f"Cards Cursor Status:           {cards_status}")
        print(f"Transactions Cursor Status:    {tx_status}")
        print(f"Last Successful Sync:          {status.last_successful_sync_at or '(never)'}")
        print(f"Last Heartbeat:                {status.last_heartbeat_at or '(never)'}")
        print(f"Last Error:                    {status.last_error or '(none)'}")
        if status.last_error_at:
            print(f"Last Error Time:               {status.last_error_at}")
        return 0
    except Exception as exc:
        print(f"ERROR: Failed to read status: {exc}", file=sys.stderr)
        return 1


def cmd_service(args: argparse.Namespace) -> int:
    """Manage Windows Service (install, remove, start, stop, debug)."""
    try:
        rc = handle_service_command(args.service_args)
        return int(rc or 0)
    except Exception as exc:
        print(f"ERROR: Windows Service operation failed: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    from poscenter_loyalty_agent import __version__

    parser = argparse.ArgumentParser(
        prog="poscenter-loyalty-agent",
        description="POSCENTER Loyalty Agent - Background Sync Service for POSCENTER ONE",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run
    p_run = subparsers.add_parser("run", help="Run the sync agent in foreground")
    p_run.add_argument("--dry-run", action="store_true", dest="dry_run", help="Execute standalone inspection dry-run")
    p_run.set_defaults(func=cmd_run)

    # check-config
    p_check = subparsers.add_parser("check-config", help="Validate configuration and state store")
    p_check.set_defaults(func=cmd_check_config)

    # status
    p_status = subparsers.add_parser("status", help="Print current synchronization checkpoints and health")
    p_status.set_defaults(func=cmd_status)

    # service
    p_service = subparsers.add_parser("service", help="Windows Service control (Windows only)")
    p_service.add_argument("service_args", nargs=argparse.REMAINDER, help="Arguments passed to win32serviceutil")
    p_service.set_defaults(func=cmd_service)

    # stage0 discovery toolkit
    from poscenter_loyalty_agent.stage0.cli import register_stage0_subparsers
    register_stage0_subparsers(subparsers)

    return parser


def cli(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    exit_code = args.func(args)
    if exit_code != 0:
        sys.exit(exit_code)


if __name__ == "__main__":
    cli()
