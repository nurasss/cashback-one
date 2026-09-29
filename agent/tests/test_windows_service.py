"""Tests for Windows Service cross-platform safety."""

import sys

import pytest

from poscenter_loyalty_agent.windows_service import (
    POSCENTERLoyaltyAgentService,
    WindowsServicePlatformError,
    handle_service_command,
)


def test_windows_service_import_and_platform_guard() -> None:
    # Importing windows_service on macOS/Linux must succeed without errors
    if sys.platform != "win32":
        with pytest.raises(WindowsServicePlatformError, match="only be instantiated on Windows"):
            POSCENTERLoyaltyAgentService()

        with pytest.raises(WindowsServicePlatformError, match="only supported on Windows"):
            handle_service_command(["install"])
