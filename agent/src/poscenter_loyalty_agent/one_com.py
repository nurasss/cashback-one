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
    """Mask password and username parameters in 1C connection strings."""
    return re.sub(
        r'(?i)(pwd|password|pass|usr|user)\s*=\s*("[^"]*"|\'[^\']*\'|[^;\s]+)',
        r'\1=***REDACTED***',
        conn_str,
    )


class OneComConnector:
    """Encapsulates connection lifecycle to 1C:Enterprise via V83.COMConnector."""

    def __init__(self, connection_string: str, existing_connection: Any = None) -> None:
        self.connection_string = connection_string
        self._connection: Any = existing_connection

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
        if self._connection is not None:
            logger.info("Reusing existing 1C COM connection.")
            return self._connection

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

        logger.debug("OneComConnector: dispatching V83.COMConnector...")
        try:
            connector = win32com.client.Dispatch("V83.COMConnector")
            logger.debug("OneComConnector: calling connector.Connect()...")
            self._connection = connector.Connect(self.connection_string)
            logger.debug("OneComConnector: connector.Connect() returned successfully!")
            logger.info("Successfully established 1C COM connection.")
            return self._connection
        except Exception as exc:
            raw_err = str(exc)
            if self.connection_string:
                raw_err = raw_err.replace(self.connection_string, "***")
            safe_err = sanitize_connection_string(raw_err)[:500]
            logger.debug("OneComConnector: Connect() failed: %s", safe_err)
            logger.error("ONE_CONNECTION_FAILED: Unable to establish COM connection: %s", safe_err)
            raise COMConnectionError(
                f"ONE_CONNECTION_FAILED: Unable to establish COM connection: {safe_err}"
            ) from None

    def disconnect(self) -> None:
        """Release COM reference."""
        if self._connection is not None:
            self._connection = None
            logger.info("Closed 1C COM connection.")
