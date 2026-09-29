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
    app_version: str = "0.2.0"
    app_env: str = "development"
    database_url: str = Field(
        default="",
        description="Database connection URL. Must be explicitly provided via environment or .env.",
    )

    redis_url: str = "redis://localhost:6379/0"

    # Agent sync limits
    sync_max_cards_batch: int = 500
    sync_max_transactions_batch: int = 1000

    @model_validator(mode="after")
    def validate_database_configuration(self) -> "Settings":
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
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

