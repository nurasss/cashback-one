"""Frozen entrypoint for POSCENTER Loyalty Windows Agent (CashbackOneAgent.exe)."""

from __future__ import annotations

import os
import sys

# Ensure SSL certificates from certifi are found in frozen bundle
try:
    import certifi
    cert_path = certifi.where()
    if os.path.exists(cert_path):
        os.environ.setdefault("SSL_CERT_FILE", cert_path)
except Exception:
    pass


def main() -> None:
    # 1. Direct service-run invocation by Windows SCM
    if len(sys.argv) > 1 and sys.argv[1] == "service-run":
        try:
            import servicemanager

            from poscenter_loyalty_agent.windows_service import POSCENTERLoyaltyAgentService

            servicemanager.Initialize()
            servicemanager.PrepareToHostSingle(POSCENTERLoyaltyAgentService)
            servicemanager.StartServiceCtrlDispatcher()
            sys.exit(0)
        except Exception as exc:
            print(f"FATAL: Service dispatcher failed: {exc}", file=sys.stderr)
            sys.exit(1)

    # 2. Launched without arguments
    if len(sys.argv) == 1:
        # Check if running under SCM (Windows Service)
        is_service = False
        try:
            import servicemanager

            from poscenter_loyalty_agent.windows_service import POSCENTERLoyaltyAgentService

            servicemanager.Initialize()
            servicemanager.PrepareToHostSingle(POSCENTERLoyaltyAgentService)
            servicemanager.StartServiceCtrlDispatcher()
            is_service = True
        except Exception:
            # Not running under SCM (error 1063 / 87), treat as interactive invocation without args
            is_service = False

        if is_service:
            sys.exit(0)

        # Interactive invocation with no arguments -> show help
        from poscenter_loyalty_agent.main import build_parser

        parser = build_parser()
        parser.print_help()
        sys.exit(0)

    # 3. Standard CLI command invocation
    from poscenter_loyalty_agent.main import cli

    cli(sys.argv[1:])


if __name__ == "__main__":
    main()
