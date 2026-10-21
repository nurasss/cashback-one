"""Environment and COM prerequisite checker for Stage 0 Discovery."""

from __future__ import annotations

import logging
import sys
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from poscenter_loyalty_agent.config import AgentSettings, get_settings

logger = logging.getLogger(__name__)

FLAG_NOT_VERIFIED = "NOT VERIFIED"
FLAG_VERIFIED = "VERIFIED"


class VerificationFlags(BaseModel):
    """Stage 0 Verification Flags."""

    real_windows_service: str = Field(default=FLAG_NOT_VERIFIED)
    real_v83_comconnector: str = Field(default=FLAG_NOT_VERIFIED)
    real_one_connection: str = Field(default=FLAG_NOT_VERIFIED)
    real_one_metadata_discovery: str = Field(default=FLAG_NOT_VERIFIED)
    real_one_mapping: str = Field(default=FLAG_NOT_VERIFIED)


class EnvironmentCheckResult(BaseModel):
    """Result of Stage 0 environment readiness inspection."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    platform: str
    is_windows: bool
    pywin32_available: bool
    com_connector_available: bool
    connection_string_configured: bool
    one_connection_successful: bool
    metadata_access_available: bool
    verification_flags: VerificationFlags
    details: list[str] = Field(default_factory=list)
    active_connection: Any = Field(default=None, exclude=True)

    def release_connection(self) -> None:
        """Explicitly release the preflight COM connection if still held."""
        if self.active_connection is not None:
            self.active_connection = None
            import gc
            gc.collect()

    def format_console(self) -> str:
        """Render a clean, secret-free summary for terminal output."""
        lines = [
            "=== Stage 0 Discovery Environment Check ===",
            f"Platform:                    {self.platform} {'(Windows)' if self.is_windows else '(Non-Windows)'}",
            f"pywin32:                     {'available' if self.pywin32_available else 'not available'}",
            f"V83.COMConnector:            {'available' if self.com_connector_available else 'not available'}",
            f"ONE Connection String:       {'configured' if self.connection_string_configured else 'not configured'}",
            f"ONE Connection:              {'successful' if self.one_connection_successful else 'skipped / failed'}",
            f"Metadata Access:             {'available' if self.metadata_access_available else 'skipped / unavailable'}",
            "",
            "--- Verification Flags ---",
            f"REAL_WINDOWS_SERVICE:        {self.verification_flags.real_windows_service}",
            f"REAL_V83_COMCONNECTOR:       {self.verification_flags.real_v83_comconnector}",
            f"REAL_ONE_CONNECTION:         {self.verification_flags.real_one_connection}",
            f"REAL_ONE_METADATA_DISCOVERY: {self.verification_flags.real_one_metadata_discovery}",
            f"REAL_ONE_MAPPING:            {self.verification_flags.real_one_mapping}",
        ]
        if self.details:
            lines.append("")
            lines.append("Details / Notes:")
            for d in self.details:
                lines.append(f" - {d}")
        return "\n".join(lines)


def check_environment(settings: AgentSettings | None = None) -> EnvironmentCheckResult:
    """Inspect environment prerequisites without reading customer data or exposing secrets.

    Guarantees cross-platform safety: never raises ModuleNotFoundError on non-Windows.
    """
    if settings is None:
        settings = get_settings()

    is_windows = sys.platform == "win32"
    platform_name = sys.platform

    pywin32_available = False
    com_connector_available = False
    connection_string_configured = bool(
        settings.one_connection_string and settings.one_connection_string.strip()
    )
    one_connection_successful = False
    metadata_access_available = False

    flags = VerificationFlags()
    details: list[str] = []

    if not is_windows:
        details.append(
            f"Current operating system is '{platform_name}'. 1C COM automation requires Windows."
        )
        return EnvironmentCheckResult(
            platform=platform_name,
            is_windows=False,
            pywin32_available=False,
            com_connector_available=False,
            connection_string_configured=connection_string_configured,
            one_connection_successful=False,
            metadata_access_available=False,
            verification_flags=flags,
            details=details,
        )

    # Windows environment inspection
    try:
        import win32com.client  # type: ignore[import-untyped]
        pywin32_available = True
    except ImportError:
        details.append("pywin32 is not installed or win32com cannot be imported.")
        return EnvironmentCheckResult(
            platform=platform_name,
            is_windows=True,
            pywin32_available=False,
            com_connector_available=False,
            connection_string_configured=connection_string_configured,
            one_connection_successful=False,
            metadata_access_available=False,
            verification_flags=flags,
            details=details,
        )

    # Check V83.COMConnector instantiation
    connector: Any = None
    try:
        connector = win32com.client.Dispatch("V83.COMConnector")
        com_connector_available = True
        flags.real_v83_comconnector = FLAG_VERIFIED
    except Exception as exc:
        details.append(f"Failed to dispatch V83.COMConnector COM object: {exc}")
        return EnvironmentCheckResult(
            platform=platform_name,
            is_windows=True,
            pywin32_available=True,
            com_connector_available=False,
            connection_string_configured=connection_string_configured,
            one_connection_successful=False,
            metadata_access_available=False,
            verification_flags=flags,
            details=details,
        )

    if not connection_string_configured:
        details.append("ONE_CONNECTION_STRING is not set in environment or configuration.")
        return EnvironmentCheckResult(
            platform=platform_name,
            is_windows=True,
            pywin32_available=True,
            com_connector_available=True,
            connection_string_configured=False,
            one_connection_successful=False,
            metadata_access_available=False,
            verification_flags=flags,
            details=details,
        )

    # Attempt read-only connection
    active_connection: Any = None
    try:
        connection = connector.Connect(settings.one_connection_string)
        one_connection_successful = True
        flags.real_one_connection = FLAG_VERIFIED

        # Test metadata access
        if hasattr(connection, "Metadata"):
            metadata_access_available = True
            active_connection = connection
            # Metadata discovery is verified ONLY after full inventory probe, not on preflight check
            details.append("1C infobase connection established; Metadata root object is accessible.")
        else:
            details.append("Connected to 1C infobase, but 'Metadata' root object was not accessible.")

    except Exception:
        details.append("Failed to establish COM connection to POSCENTER ONE infobase.")

    return EnvironmentCheckResult(
        platform=platform_name,
        is_windows=True,
        pywin32_available=pywin32_available,
        com_connector_available=com_connector_available,
        connection_string_configured=connection_string_configured,
        one_connection_successful=one_connection_successful,
        metadata_access_available=metadata_access_available,
        verification_flags=flags,
        details=details,
        active_connection=active_connection,
    )
