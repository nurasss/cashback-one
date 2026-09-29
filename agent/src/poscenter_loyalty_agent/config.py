"""Configuration management for POSCENTER Loyalty Windows Agent."""
import os
import sys
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_default_data_dir() -> Path:
    """Resolve default application data directory across platforms."""
    if sys.platform == "win32":
        program_data = os.environ.get("ProgramData", r"C:\ProgramData")
        return Path(program_data) / "POSCENTER" / "LoyaltyAgent"
    return Path.home() / ".poscenter_loyalty_agent"


class AgentSettings(BaseSettings):
    """Runtime configuration for POSCENTER Loyalty Agent."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    agent_env: str = Field(
        default="development",
        description="Execution environment: 'development', 'production', or 'test'",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    agent_cloud_base_url: str = Field(
        default="http://localhost:8000",
        description="Base URL for Cloud Backend API",
    )
    agent_api_key: str = Field(
        default="",
        description="Secret Agent Key sent in X-Agent-Key header",
    )
    agent_poll_interval_seconds: int = Field(
        default=120,
        ge=1,
        le=86400,
        description="Interval between sync cycles in seconds",
    )
    agent_heartbeat_interval_seconds: int = Field(
        default=60,
        ge=1,
        le=86400,
        description="Interval between heartbeats in seconds",
    )
    agent_http_timeout_seconds: float = Field(
        default=30.0,
        ge=1.0,
        le=300.0,
        description="HTTP request timeout in seconds",
    )
    agent_card_batch_size: int = Field(
        default=100,
        ge=1,
        le=500,
        description="Maximum cards per Cloud sync batch (backend limit is 500)",
    )
    agent_tx_batch_size: int = Field(
        default=200,
        ge=1,
        le=1000,
        description="Maximum transactions per Cloud sync batch (backend limit is 1000)",
    )
    agent_max_pages_per_cycle: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum source pages processed in a single poll cycle",
    )
    agent_sync_backoff_initial_seconds: float = Field(
        default=2.0,
        gt=0.0,
        description="Initial retry backoff delay in seconds",
    )
    agent_sync_backoff_max_seconds: float = Field(
        default=300.0,
        ge=1.0,
        description="Maximum retry backoff delay in seconds",
    )
    agent_sync_backoff_jitter_ratio: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Random jitter ratio applied to retry backoff",
    )
    agent_shutdown_grace_seconds: float = Field(
        default=30.0,
        ge=0.0,
        description="Grace period in seconds for in-flight sync operations on shutdown",
    )
    agent_state_db_path: Path | None = Field(
        default=None,
        description="Path to SQLite durable state database",
    )
    agent_log_dir: Path | None = Field(
        default=None,
        description="Directory for rotating log files",
    )
    agent_version: str = Field(
        default="0.1.0",
        description="Agent release version",
    )
    one_adapter_mode: str = Field(
        default="stub",
        description="POSCENTER ONE adapter mode: 'stub', 'fake', or 'com'",
    )
    one_connection_string: str = Field(
        default="",
        description="Connection string for V83.COMConnector (treated as secret)",
    )
    log_max_bytes: int = Field(
        default=10_485_760,
        ge=1024,
        validation_alias=AliasChoices("log_max_bytes", "agent_log_max_bytes"),
        description="Maximum log file size before rotation (bytes)",
    )
    log_backup_count: int = Field(
        default=5,
        ge=1,
        le=50,
        validation_alias=AliasChoices("log_backup_count", "agent_log_backup_count"),
        description="Number of rotating log backups to retain",
    )

    @field_validator("agent_env")
    @classmethod
    def validate_agent_env(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean not in ("development", "production", "test"):
            raise ValueError(f"Invalid AGENT_ENV '{v}'. Allowed: development, production, test")
        return clean

    @field_validator("one_adapter_mode")
    @classmethod
    def validate_adapter_mode(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean not in ("stub", "fake", "com"):
            raise ValueError(f"Invalid ONE_ADAPTER_MODE '{v}'. Allowed: stub, fake, com")
        return clean

    @model_validator(mode="after")
    def validate_security_and_paths(self) -> "AgentSettings":
        # Normalize and validate Cloud Base URL
        url = self.agent_cloud_base_url.strip().rstrip("/")
        if not url:
            raise ValueError("AGENT_CLOUD_BASE_URL must be non-empty")
        if self.agent_env == "production":
            if not url.startswith("https://"):
                raise ValueError("AGENT_CLOUD_BASE_URL must use HTTPS in production")
        else:
            if not (url.startswith("http://") or url.startswith("https://")):
                raise ValueError("AGENT_CLOUD_BASE_URL must start with http:// or https://")
        self.agent_cloud_base_url = url

        # Validate API Key
        clean_api_key = self.agent_api_key.strip()
        if self.agent_env == "production":
            if not clean_api_key:
                raise ValueError("AGENT_API_KEY is required in production")
            if len(clean_api_key) < 16:
                raise ValueError("AGENT_API_KEY must be at least 16 characters in production")
        self.agent_api_key = clean_api_key

        # Adapter mode restrictions
        if self.one_adapter_mode == "fake" and self.agent_env != "test":
            raise ValueError("ONE_ADAPTER_MODE='fake' is strictly forbidden outside AGENT_ENV=test")

        if self.one_adapter_mode == "com" and self.agent_env == "production":
            if not self.one_connection_string.strip():
                raise ValueError("ONE_CONNECTION_STRING is required when ONE_ADAPTER_MODE='com' in production")

        # Validate backoff bounds
        if self.agent_sync_backoff_max_seconds < self.agent_sync_backoff_initial_seconds:
            raise ValueError(
                f"AGENT_SYNC_BACKOFF_MAX_SECONDS ({self.agent_sync_backoff_max_seconds}) "
                f"must be >= AGENT_SYNC_BACKOFF_INITIAL_SECONDS ({self.agent_sync_backoff_initial_seconds})"
            )

        # Resolve default paths if not explicitly provided
        base_dir = get_default_data_dir()
        if self.agent_state_db_path is None:
            self.agent_state_db_path = base_dir / "state" / "agent_state.db"
        if self.agent_log_dir is None:
            self.agent_log_dir = base_dir / "logs"

        return self

    @property
    def state_db_path(self) -> Path:
        assert self.agent_state_db_path is not None
        return self.agent_state_db_path

    @property
    def lock_file_path(self) -> Path:
        return self.state_db_path.parent / "agent.lock"

    @property
    def log_file_path(self) -> Path:
        assert self.agent_log_dir is not None
        return self.agent_log_dir / "agent.log"

    @property
    def cloud_api_base_url(self) -> str:
        return self.agent_cloud_base_url

    @property
    def cloud_api_timeout_seconds(self) -> float:
        return self.agent_http_timeout_seconds

    @property
    def cloud_api_verify_ssl(self) -> bool:
        """TLS certificate verification is enabled by default across ALL environments."""
        return True

    @property
    def sync_interval_seconds(self) -> int:
        return self.agent_poll_interval_seconds

    @property
    def heartbeat_interval_seconds(self) -> int:
        return self.agent_heartbeat_interval_seconds

    @property
    def batch_size_cards(self) -> int:
        return self.agent_card_batch_size

    @property
    def batch_size_transactions(self) -> int:
        return self.agent_tx_batch_size

    @property
    def max_pages_per_cycle(self) -> int:
        return self.agent_max_pages_per_cycle

    @property
    def shutdown_grace_seconds(self) -> float:
        return self.agent_shutdown_grace_seconds

    @property
    def sync_backoff_initial_seconds(self) -> float:
        return self.agent_sync_backoff_initial_seconds

    @property
    def sync_backoff_max_seconds(self) -> float:
        return self.agent_sync_backoff_max_seconds

    @property
    def sync_backoff_jitter_ratio(self) -> float:
        return self.agent_sync_backoff_jitter_ratio


def get_agent_settings() -> AgentSettings:
    """Instantiate AgentSettings with current environment."""
    return AgentSettings()


get_settings = get_agent_settings
