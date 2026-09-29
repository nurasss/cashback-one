import re
from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "POSCENTER Loyalty Backend"
    app_version: str = "0.4.0"
    app_env: str = "development"
    database_url: str = Field(
        default="",
        description="Database connection URL. Must be explicitly provided via environment or .env.",
    )
    redis_url: str = Field(
        default="",
        description="Redis connection URL for rate limiting and cache. Required in dev/prod.",
    )

    # Auth secrets & configuration (TASK-003)
    jwt_signing_key: str = Field(
        default="",
        description="HMAC secret key for signing customer access JWTs (min 32 chars).",
    )
    auth_challenge_hash_key: str = Field(
        default="",
        description="HMAC secret key for challenge code digests (min 32 chars).",
    )
    whatsapp_login_number: str = Field(
        default="",
        description="WhatsApp business login number in E.164 format (+77001234567).",
    )

    # Wappi Webhook Configuration (TASK-004)
    wappi_login_profile_id: str = Field(
        default="",
        description="Wappi WhatsApp instance/profile ID for login messages.",
    )
    wappi_webhook_auth_header: str = Field(
        default="",
        description="Header name used to authenticate incoming Wappi webhooks (must be explicitly configured).",
    )
    wappi_webhook_auth_secret: str = Field(
        default="",
        description="Shared secret for incoming Wappi webhook authentication (min 32 chars).",
    )
    wappi_webhook_max_body_bytes: int = Field(
        default=65536,
        description="Maximum allowed body size for Wappi webhook requests (default 64KB).",
    )

    # Auth TTL and limits
    challenge_ttl_seconds: int = 180  # 3 minutes
    access_token_ttl_seconds: int = 900  # 15 minutes
    refresh_token_ttl_seconds: int = 30 * 86400  # 30 days

    auth_challenge_device_limit: int = 5
    auth_challenge_ip_limit: int = 20
    auth_challenge_rate_window_seconds: int = 300

    # Agent sync limits
    sync_max_cards_batch: int = 500
    sync_max_transactions_batch: int = 1000

    @model_validator(mode="after")
    def validate_configuration(self) -> "Settings":
        db_url = self.database_url.strip() if self.database_url else ""
        if not db_url:
            raise ValueError(
                "DATABASE_URL must be explicitly provided in environment or .env"
            )
        if self.app_env.lower() != "test" and db_url.startswith("sqlite"):
            raise ValueError(
                "DATABASE_URL must be a valid PostgreSQL connection string in development/production. "
                "SQLite is only permitted when APP_ENV=test."
            )

        if self.app_env.lower() == "test":
            # Provide deterministic defaults for test execution
            if not self.redis_url:
                self.redis_url = "redis://localhost:6379/15"
            if not self.jwt_signing_key:
                self.jwt_signing_key = "test_jwt_signing_key_at_least_32_chars_long_12345"
            if not self.auth_challenge_hash_key:
                self.auth_challenge_hash_key = "test_challenge_hash_key_at_least_32_chars_long_12345"
            if not self.whatsapp_login_number:
                self.whatsapp_login_number = "+77001234567"
            if not self.wappi_login_profile_id:
                self.wappi_login_profile_id = "test-wappi-login-profile"
            if not self.wappi_webhook_auth_header:
                self.wappi_webhook_auth_header = "X-Test-Wappi-Auth"
            if not self.wappi_webhook_auth_secret:
                self.wappi_webhook_auth_secret = "test_wappi_webhook_secret_min_32_characters_12345"
        else:
            if not self.redis_url or not self.redis_url.strip():
                raise ValueError("REDIS_URL must be explicitly provided in environment or .env")
            if not self.jwt_signing_key or len(self.jwt_signing_key.strip()) < 32:
                raise ValueError("JWT_SIGNING_KEY must be provided and be at least 32 characters long")
            if not self.auth_challenge_hash_key or len(self.auth_challenge_hash_key.strip()) < 32:
                raise ValueError("AUTH_CHALLENGE_HASH_KEY must be provided and be at least 32 characters long")
            if not self.wappi_login_profile_id or not self.wappi_login_profile_id.strip():
                raise ValueError("WAPPI_LOGIN_PROFILE_ID must be provided in environment or .env")
            if not self.wappi_webhook_auth_header or not self.wappi_webhook_auth_header.strip():
                raise ValueError("WAPPI_WEBHOOK_AUTH_HEADER must be provided in environment or .env")
            if not self.wappi_webhook_auth_secret or len(self.wappi_webhook_auth_secret.strip()) < 32:
                raise ValueError("WAPPI_WEBHOOK_AUTH_SECRET must be provided and be at least 32 characters long")

        # Validate WHATSAPP_LOGIN_NUMBER format (E.164)
        if not self.whatsapp_login_number or not self.whatsapp_login_number.strip():
            raise ValueError("WHATSAPP_LOGIN_NUMBER must be provided in environment or .env")
        self.whatsapp_login_number = self.whatsapp_login_number.strip()
        if not re.match(r"^\+[1-9]\d{7,14}$", self.whatsapp_login_number):
            raise ValueError(
                "WHATSAPP_LOGIN_NUMBER must be in valid E.164 format (+[1-9] followed by 7-14 digits, e.g. +77001234567)"
            )

        return self



@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

