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
    app_version: str = "0.3.0"
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
        else:
            if not self.redis_url or not self.redis_url.strip():
                raise ValueError("REDIS_URL must be explicitly provided in environment or .env")
            if not self.jwt_signing_key or len(self.jwt_signing_key.strip()) < 32:
                raise ValueError("JWT_SIGNING_KEY must be provided and be at least 32 characters long")
            if not self.auth_challenge_hash_key or len(self.auth_challenge_hash_key.strip()) < 32:
                raise ValueError("AUTH_CHALLENGE_HASH_KEY must be provided and be at least 32 characters long")
            if not self.whatsapp_login_number or not self.whatsapp_login_number.strip():
                raise ValueError("WHATSAPP_LOGIN_NUMBER must be provided in environment or .env")

        return self



@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

