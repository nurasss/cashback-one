"""Windows Service Framework integration for POSCENTER Loyalty Agent.

CRITICAL: Cross-platform safe.
On macOS/Linux, win32serviceutil is not imported and helper functions fail cleanly
with PlatformError without breaking unit tests or tooling.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
from typing import Any

from poscenter_loyalty_agent.config import get_settings
from poscenter_loyalty_agent.logging import configure_logging
from poscenter_loyalty_agent.runtime import AgentRuntime

logger = logging.getLogger(__name__)


class WindowsServicePlatformError(RuntimeError):
    """Raised when attempting Windows Service operations on a non-Windows platform."""


# On Windows, win32serviceutil is available. On POSIX/macOS, provide dummy base.
if sys.platform == "win32":
    try:
        import servicemanager  # type: ignore[import-untyped]
        import win32event  # type: ignore[import-untyped]
        import win32service  # type: ignore[import-untyped]
        import win32serviceutil  # type: ignore[import-untyped]

        BaseServiceClass = win32serviceutil.ServiceFramework
    except ImportError:
        servicemanager = None  # type: ignore[assignment]
        win32event = None  # type: ignore[assignment]
        win32service = None  # type: ignore[assignment]
        win32serviceutil = None  # type: ignore[assignment]
        BaseServiceClass = object  # type: ignore[misc,assignment]
else:
    servicemanager = None  # type: ignore[assignment]
    win32event = None  # type: ignore[assignment]
    win32service = None  # type: ignore[assignment]
    win32serviceutil = None  # type: ignore[assignment]
    BaseServiceClass = object  # type: ignore[misc,assignment]


class POSCENTERLoyaltyAgentService(BaseServiceClass):  # type: ignore[valid-type,misc]
    """Windows Service wrapper for POSCENTER Loyalty Agent."""

    _svc_name_ = "POSCENTERLoyaltyAgent"
    _svc_display_name_ = "POSCENTER Loyalty Agent Service"
    _svc_description_ = "Background synchronization service for POSCENTER Loyalty system."

    def __init__(self, args: Any = None) -> None:
        if sys.platform != "win32":
            raise WindowsServicePlatformError("POSCENTERLoyaltyAgentService can only be instantiated on Windows.")

        super().__init__(args)
        self.stop_event: Any = win32event.CreateEvent(None, 0, 0, None) if win32event else None
        self.runtime: AgentRuntime | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None

    def ReportServiceStatus(self, status: Any) -> None:
        """Report status to SCM (overridden by ServiceFramework on Windows)."""
        super_report = getattr(super(), "ReportServiceStatus", None)
        if callable(super_report):
            super_report(status)

    def SvcStop(self) -> None:
        """Called by Windows SCM to request service stop."""
        if win32service:
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        logger.info("Service stop signal received from SCM.")
        if win32event and self.stop_event:
            win32event.SetEvent(self.stop_event)
        if self.runtime and self._loop:
            self._loop.call_soon_threadsafe(self.runtime.request_stop)

    def SvcDoRun(self) -> None:
        """Main service execution called by Windows SCM."""
        if servicemanager:
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, ""),
            )

        settings = get_settings()
        configure_logging(
            log_level=settings.log_level,
            log_file_path=settings.log_file_path,
            max_bytes=settings.log_max_bytes,
            backup_count=settings.log_backup_count,
        )
        logger.info("Starting %s via Windows Service Manager...", self._svc_name_)

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self.runtime = AgentRuntime(settings=settings)

        try:
            self._loop.run_until_complete(self.runtime.run())
        except Exception as exc:
            logger.exception("Agent service encountered unhandled error: %s", exc)
        finally:
            self._loop.close()
            if servicemanager:
                servicemanager.LogMsg(
                    servicemanager.EVENTLOG_INFORMATION_TYPE,
                    servicemanager.PYS_SERVICE_STOPPED,
                    (self._svc_name_, ""),
                )


if getattr(sys, "frozen", False):
    POSCENTERLoyaltyAgentService._exe_name_ = sys.executable
    POSCENTERLoyaltyAgentService._exe_args_ = "service-run"


def handle_service_command(argv: list[str]) -> int:
    """Entrypoint to install, update, remove, debug, start, or stop Windows Service."""
    if sys.platform != "win32":
        raise WindowsServicePlatformError("Windows Service command-line management is only supported on Windows.")

    import win32serviceutil  # type: ignore[import-untyped]

    prog = sys.argv[0] if sys.argv else "poscenter-loyalty-agent"
    if not argv:
        full_argv = [prog]
    elif argv[0] == prog or argv[0] == sys.executable:
        full_argv = list(argv)
    else:
        full_argv = [prog] + list(argv)

    err = win32serviceutil.HandleCommandLine(POSCENTERLoyaltyAgentService, argv=full_argv)
    return int(err or 0)

