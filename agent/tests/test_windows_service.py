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


def test_windows_service_logging_config_propagation() -> None:
    """Windows Service must configure logging using settings log_max_bytes and log_backup_count."""
    from unittest.mock import patch

    from poscenter_loyalty_agent.config import AgentSettings

    captured_kwargs: dict[str, object] = {}

    def fake_configure_logging(**kwargs: object) -> None:
        captured_kwargs.update(kwargs)

    dummy_settings = AgentSettings(
        agent_api_key="test-api-key",
        log_max_bytes=987654,
        log_backup_count=8,
    )

    with patch("poscenter_loyalty_agent.windows_service.get_settings", return_value=dummy_settings), \
         patch("poscenter_loyalty_agent.windows_service.configure_logging", side_effect=fake_configure_logging), \
         patch("asyncio.new_event_loop") as mock_loop_cls, \
         patch("asyncio.set_event_loop"), \
         patch("poscenter_loyalty_agent.windows_service.AgentRuntime"):
        mock_loop = mock_loop_cls.return_value
        mock_loop.run_until_complete.return_value = None

        service = object.__new__(POSCENTERLoyaltyAgentService)
        service.runtime = None
        service._loop = None
        service.SvcDoRun()

    assert captured_kwargs.get("max_bytes") == 987654
    assert captured_kwargs.get("backup_count") == 8
