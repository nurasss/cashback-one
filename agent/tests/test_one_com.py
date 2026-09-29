"""Tests for 1C COM connection boundary and password sanitization."""

import sys

import pytest

from poscenter_loyalty_agent.one_com import (
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
