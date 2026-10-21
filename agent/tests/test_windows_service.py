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
         patch("poscenter_loyalty_agent.windows_service.servicemanager"), \
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


def test_handle_service_command_argument_routing() -> None:
    """Service command arguments must be properly framed with argv[0] for HandleCommandLine."""
    if sys.platform != "win32":
        pytest.skip("Windows only test")

    from unittest.mock import MagicMock, patch

    mock_hcl = MagicMock(return_value=0)
    with patch("win32serviceutil.HandleCommandLine", mock_hcl):
        rc = handle_service_command(["install"])
        assert rc == 0
        mock_hcl.assert_called_once()
        args, kwargs = mock_hcl.call_args
        passed_cls = args[0]
        passed_argv = kwargs.get("argv") if "argv" in kwargs else (args[2] if len(args) > 2 else None)
        assert passed_cls is POSCENTERLoyaltyAgentService
        assert passed_argv is not None
        assert len(passed_argv) >= 2
        assert passed_argv[1] == "install"


@pytest.mark.parametrize("mock_exit_code", [0, 5, 1060])
def test_handle_service_command_error_codes(mock_exit_code: int) -> None:
    """handle_service_command must return the exact error code from HandleCommandLine."""
    if sys.platform != "win32":
        pytest.skip("Windows only test")

    from unittest.mock import MagicMock, patch

    mock_hcl = MagicMock(return_value=mock_exit_code)
    with patch("win32serviceutil.HandleCommandLine", mock_hcl):
        rc = handle_service_command(["start"])
        assert rc == mock_exit_code


@pytest.mark.parametrize("mock_exit_code", [0, 5, 1060])
def test_cmd_service_propagates_exit_code(mock_exit_code: int) -> None:
    """cmd_service CLI handler must return non-zero exit codes upon failure."""
    import argparse
    from unittest.mock import patch

    from poscenter_loyalty_agent.main import cmd_service

    args = argparse.Namespace(service_args=["install"])
    with patch("poscenter_loyalty_agent.main.handle_service_command", return_value=mock_exit_code):
        rc = cmd_service(args)
        assert rc == mock_exit_code

