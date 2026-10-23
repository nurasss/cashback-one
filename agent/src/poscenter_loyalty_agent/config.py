"""Configuration management for POSCENTER Loyalty Windows Agent."""
import os
import sys
from ipaddress import IPv4Network, IPv6Network, ip_address, ip_network
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
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
        env_file=(".env", str(get_default_data_dir() / "config" / ".env.service")),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        hide_input_in_errors=True,
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
    agent_pos_server_enabled: bool = False
    agent_pos_listen_host: str = "0.0.0.0"
    agent_pos_listen_port: int = 8765
    agent_pos_token: SecretStr = Field(default=SecretStr(""), repr=False, exclude=True)
    agent_pos_allowed_networks: str = "127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"
    agent_pos_cloud_timeout_seconds: float = Field(default=5.0, gt=0, le=5, allow_inf_nan=False)
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
        default="0.2.1",
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
    agent_one_timezone: str = Field(
        default="Asia/Almaty",
        description="Timezone of 1C infobase (default: Asia/Almaty)",
    )
    agent_one_lookback_days: int = Field(
        default=3,
        ge=1,
        le=30,
        description="Sliding lookback window in days for transactions",
    )
    agent_one_initial_history_days: int = Field(
        default=0,
        ge=0,
        description="Initial history window in days for transactions (0 = all history from 1990-01-01)",
    )
    agent_one_max_window_rows: int = Field(
        default=300_000,
        ge=1,
        description="Maximum allowed rows in transaction window query",
    )
    agent_clamp_negative_balance: bool = Field(
        default=False,
        description="отправлять в облако max(0, баланс); по умолчанию False (отрицательные остатки передаются как есть); настоящий отрицательный остаток остаётся в 1С",
    )
    one_mapping_path: Path | None = Field(
        default=None,
        description="Path to Stage 0 verified mapping JSON file",
    )
    one_state_key_path: Path | None = Field(
        default=None,
        description="Path to local HMAC secret key file for card content hashing",
    )
    dry_run: bool = Field(
        default=False,
        description="Dry-run execution mode without mutating cloud state",
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
    def validate_pos_server(self) -> "AgentSettings":
        if not self.agent_pos_server_enabled:
            return self
        token = self.agent_pos_token.get_secret_value()
        if len(token) < 32 or any(not 33 <= ord(char) <= 126 for char in token):
            raise ValueError("AGENT_POS_TOKEN: минимум 32 печатных ASCII-символа без пробелов")
        try:
            ip_address(self.agent_pos_listen_host)
        except ValueError:
            raise ValueError("AGENT_POS_LISTEN_HOST: требуется IP-адрес IPv4 или IPv6") from None
        if not 1 <= self.agent_pos_listen_port <= 65535:
            raise ValueError("AGENT_POS_LISTEN_PORT: требуется порт от 1 до 65535")
        try:
            if not self.pos_allowed_networks:
                raise ValueError("Empty POS CIDR list")
        except ValueError:
            raise ValueError("AGENT_POS_ALLOWED_NETWORKS: требуется непустой список CIDR через запятую") from None
        return self

    @property
    def pos_allowed_networks(self) -> tuple[IPv4Network | IPv6Network, ...]:
        parts = self.agent_pos_allowed_networks.split(",")
        if not all(part.strip() and "/" in part for part in parts):
            raise ValueError("Invalid POS CIDR list")
        return tuple(ip_network(part.strip(), strict=True) for part in parts)

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
        if self.one_mapping_path is None:
            self.one_mapping_path = base_dir / "mapping" / "stage0_mapping.json"
        if self.one_state_key_path is None:
            self.one_state_key_path = base_dir / "state" / "agent_state.key"

        if self.one_adapter_mode == "com" and self.agent_env == "production":
            if not self.one_connection_string.strip():
                raise ValueError("ONE_CONNECTION_STRING is required when ONE_ADAPTER_MODE='com' in production")
            if not self.one_mapping_path.exists():
                raise ValueError(
                    f"Valid ONE_MAPPING_PATH pointing to existing file is required when ONE_ADAPTER_MODE='com' in production: {self.one_mapping_path}"
                )

        return self

    @property
    def mapping_path(self) -> Path:
        assert self.one_mapping_path is not None
        return self.one_mapping_path

    @property
    def state_key_path(self) -> Path:
        assert self.one_state_key_path is not None
        return self.one_state_key_path

    @property
    def lookback_days(self) -> int:
        return self.agent_one_lookback_days

    @property
    def one_timezone(self) -> str:
        return self.agent_one_timezone

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
