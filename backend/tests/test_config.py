import os

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_config_dev_without_database_url_raises_validation_error() -> None:
    """Fail-fast: in development/production, missing DATABASE_URL must raise ValidationError."""
    old_db_url = os.environ.pop("DATABASE_URL", None)
    old_env = os.environ.get("APP_ENV")
    try:
        os.environ["APP_ENV"] = "development"
        with pytest.raises(ValidationError):
            Settings(_env_file=None)
    finally:
        if old_db_url is not None:
            os.environ["DATABASE_URL"] = old_db_url
        if old_env is not None:
            os.environ["APP_ENV"] = old_env


def test_config_test_with_explicit_sqlite_allowed() -> None:
    """SQLite in-memory is permitted when APP_ENV=test."""
    cfg = Settings(
        app_env="test",
        database_url="sqlite+aiosqlite:///:memory:",
        _env_file=None,
    )
    assert cfg.app_env == "test"
    assert cfg.database_url == "sqlite+aiosqlite:///:memory:"


def test_config_dev_with_postgres_url_allowed() -> None:
    """PostgreSQL URL is valid in development."""
    cfg = Settings(
        app_env="development",
        database_url="postgresql+asyncpg://loyalty:secret@localhost:5432/poscenter",
        _env_file=None,
    )
    assert cfg.app_env == "development"
    assert "postgresql+asyncpg" in cfg.database_url


def test_config_dev_with_sqlite_rejected() -> None:
    """Disallow silent or explicit SQLite fallback in development/production."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            app_env="development",
            database_url="sqlite+aiosqlite:///:memory:",
            _env_file=None,
        )
    assert "SQLite is only permitted when APP_ENV=test" in str(exc_info.value)
