"""Tests for 1C COM connection boundary, exception hygiene, and secrecy."""

import logging
import sys
from unittest.mock import MagicMock, patch

import pytest

from poscenter_loyalty_agent.one_com import (
    COMConnectionError,
    COMPlatformUnsupportedError,
    OneComConnector,
    sanitize_connection_string,
)


def test_sanitize_connection_string() -> None:
    conn_str = "File='C:\\1C\\db';Usr='Administrator';Pwd='SuperSecretPassword123';"
    sanitized = sanitize_connection_string(conn_str)
    assert "SuperSecretPassword123" not in sanitized
    assert "Pwd=***REDACTED***" in sanitized
    assert "Usr='Administrator'" in sanitized


def test_com_platform_guard_on_non_windows() -> None:
    connector = OneComConnector("File='test';")
    if sys.platform != "win32":
        assert not connector.is_supported()
        with pytest.raises(COMPlatformUnsupportedError, match="only supported on Windows"):
            connector.connect()
    else:
        assert connector.is_supported()


def test_com_exception_hygiene_zero_secret_leak(caplog: pytest.LogCaptureFixture) -> None:
    """Underlying COM exception must never leak database path, user, or password into error or logs."""
    secret_conn = "File='C:\\SecretDb';Usr='admin';Pwd='supersecret';"
    connector = OneComConnector(secret_conn)

    # Simulate running on Windows with an underlying exception carrying the connection string
    with patch.object(OneComConnector, "is_supported", return_value=True):
        mock_win32com = MagicMock()
        mock_dispatch = MagicMock()
        mock_dispatch.Connect.side_effect = RuntimeError(
            f"COM Dispatch failed connecting to {secret_conn}: catastrophic error"
        )
        mock_win32com.client.Dispatch.return_value = mock_dispatch

        with patch.dict("sys.modules", {"win32com": mock_win32com, "win32com.client": mock_win32com.client}):
            with caplog.at_level(logging.DEBUG):
                with pytest.raises(COMConnectionError) as exc_info:
                    connector.connect()

    err_str = str(exc_info.value)
    # Verify exception message contains NO secrets
    assert "SecretDb" not in err_str
    assert "admin" not in err_str
    assert "supersecret" not in err_str
    assert "ONE_CONNECTION_FAILED" in err_str

    # Verify captured logs contain NO secrets
    for record in caplog.records:
        assert "SecretDb" not in record.message
        assert "admin" not in record.message
        assert "supersecret" not in record.message
