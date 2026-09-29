"""Boundary and connection seam for 1C:Enterprise COM connector (V83.COMConnector).

CRITICAL CONSTRAINTS:
1. No 1C metadata object names are hardcoded here (Stage 0 discovery is required first).
2. Cross-platform safe: pywin32 / win32com is only loaded dynamically on Windows.
3. The ENTIRE connection string is treated as a secret: never logged or included in exceptions.
"""

from __future__ import annotations

import logging
import re
import sys
from typing import Any

logger = logging.getLogger(__name__)


class COMPlatformUnsupportedError(RuntimeError):
    """Raised when attempting COM operations on a non-Windows platform."""


class COMConnectionError(RuntimeError):
    """Raised when COM connection to POSCENTER ONE fails."""


def sanitize_connection_string(conn_str: str) -> str:
    """Mask password parameters in 1C connection strings (utility for isolated tests)."""
    return re.sub(r'(?i)(pwd|password|pass)\s*=\s*[^;\s]+', r'\1=***REDACTED***', conn_str)


class OneComConnector:
    """Encapsulates connection lifecycle to 1C:Enterprise via V83.COMConnector."""

    def __init__(self, connection_string: str) -> None:
        self.connection_string = connection_string
        self._connection: Any = None

    @classmethod
    def is_supported(cls) -> bool:
        """Returns True only when running on a Windows environment."""
        return sys.platform == "win32"

    def connect(self) -> Any:
        """Establish COM connection to 1C infobase.

        Raises COMPlatformUnsupportedError on non-Windows platforms.
        Raises COMConnectionError if COM connector instantiation or Connect() fails.
        Guarantees zero connection string leakage into logs or exception messages.
        """
        if not self.is_supported():
            raise COMPlatformUnsupportedError(
                f"V83.COMConnector is only supported on Windows. Current platform is {sys.platform}."
            )

        # Entire connection string is treated as secret - zero connection details logged
        logger.info("Connecting to POSCENTER ONE via COM")

        try:
            import win32com.client  # type: ignore[import-untyped]
        except ImportError:
            logger.error("ONE_CONNECTION_FAILED: pywin32 / win32com is not installed.")
            raise COMConnectionError(
                "ONE_CONNECTION_FAILED: pywin32 / win32com is not installed on this Windows environment."
            ) from None

        try:
            connector = win32com.client.Dispatch("V83.COMConnector")
            self._connection = connector.Connect(self.connection_string)
            logger.info("Successfully established 1C COM connection.")
            return self._connection
        except Exception:
            logger.error("ONE_CONNECTION_FAILED: Unable to establish COM connection.")
            raise COMConnectionError("ONE_CONNECTION_FAILED: Unable to establish COM connection.") from None

    def disconnect(self) -> None:
        """Release COM reference."""
        if self._connection is not None:
            self._connection = None
            logger.info("Closed 1C COM connection.")
