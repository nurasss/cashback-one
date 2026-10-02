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
    """PostgreSQL URL and full valid secrets in development are allowed."""
    cfg = Settings(
        app_env="development",
        database_url="postgresql+asyncpg://loyalty:secret@localhost:5432/poscenter",
        redis_url="redis://localhost:6379/0",
        jwt_signing_key="a" * 32,
        admin_jwt_signing_key="z" * 32,
        admin_allowed_origins=["https://admin.test"],
        auth_challenge_hash_key="b" * 32,
        whatsapp_login_number="+77001234567",
        sms_otp_hash_key="d" * 32,
        wappi_login_profile_id="prod-profile-id-12345",
        wappi_webhook_auth_header="X-Custom-Auth-Header",
        wappi_webhook_auth_secret="c" * 32,
        _env_file=None,
    )
    assert cfg.app_env == "development"
    assert "postgresql+asyncpg" in cfg.database_url
    assert cfg.wappi_login_profile_id == "prod-profile-id-12345"
    assert cfg.sms_otp_hash_key == "d" * 32


def test_config_dev_without_redis_url_rejected() -> None:
    """In development, missing REDIS_URL must be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            app_env="development",
            database_url="postgresql+asyncpg://loyalty:secret@localhost:5432/poscenter",
            redis_url="",
            jwt_signing_key="a" * 32,
            auth_challenge_hash_key="b" * 32,
            whatsapp_login_number="+77001234567",
            _env_file=None,
        )
    assert "REDIS_URL must be explicitly provided" in str(exc_info.value)


def test_config_dev_short_jwt_signing_key_rejected() -> None:
    """JWT_SIGNING_KEY shorter than 32 characters must be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            app_env="development",
            database_url="postgresql+asyncpg://loyalty:secret@localhost:5432/poscenter",
            redis_url="redis://localhost:6379/0",
            jwt_signing_key="too_short_key",
            auth_challenge_hash_key="b" * 32,
            whatsapp_login_number="+77001234567",
            _env_file=None,
        )
    assert "JWT_SIGNING_KEY" in str(exc_info.value)


def test_config_dev_short_auth_challenge_hash_key_rejected() -> None:
    """AUTH_CHALLENGE_HASH_KEY shorter than 32 characters must be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            app_env="development",
            database_url="postgresql+asyncpg://loyalty:secret@localhost:5432/poscenter",
            redis_url="redis://localhost:6379/0",
            jwt_signing_key="a" * 32,
            auth_challenge_hash_key="short",
            whatsapp_login_number="+77001234567",
            _env_file=None,
        )
    assert "AUTH_CHALLENGE_HASH_KEY" in str(exc_info.value)



def test_config_dev_with_sqlite_rejected() -> None:
    """Disallow silent or explicit SQLite fallback in development/production."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            app_env="development",
            database_url="sqlite+aiosqlite:///:memory:",
            _env_file=None,
        )
    assert "SQLite is only permitted when APP_ENV=test" in str(exc_info.value)


@pytest.mark.parametrize(
    "invalid_phone",
    [
        "abc",
        "77001234567",  # Missing leading +
        "+0123456789",  # First digit after + cannot be 0 in E.164
        "+7",  # Too short
        "+7" + "1" * 15,  # Too long (>15 digits total)
        "+7 700 123 45 67",  # Spaces inside not allowed
        "+7-700-123-45-67",  # Hyphens not allowed
    ],
)
def test_config_invalid_whatsapp_login_number_rejected(invalid_phone: str) -> None:
    """WHATSAPP_LOGIN_NUMBER must strictly follow E.164 format."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            app_env="test",
            database_url="sqlite+aiosqlite:///:memory:",
            whatsapp_login_number=invalid_phone,
            _env_file=None,
        )
    assert "WHATSAPP_LOGIN_NUMBER must be in valid E.164 format" in str(exc_info.value)


def test_config_dev_missing_wappi_login_profile_id_rejected() -> None:
    """WAPPI_LOGIN_PROFILE_ID must be provided in development/production."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            app_env="development",
            database_url="postgresql+asyncpg://loyalty:secret@localhost:5432/poscenter",
            redis_url="redis://localhost:6379/0",
            jwt_signing_key="a" * 32,
            auth_challenge_hash_key="b" * 32,
            sms_otp_hash_key="d" * 32,
            whatsapp_login_number="+77001234567",
            wappi_login_profile_id="",
            wappi_webhook_auth_header="X-Test-Auth-Header",
            wappi_webhook_auth_secret="c" * 32,
            _env_file=None,
        )
    assert "WAPPI_LOGIN_PROFILE_ID" in str(exc_info.value)


def test_config_dev_short_wappi_webhook_auth_secret_rejected() -> None:
    """WAPPI_WEBHOOK_AUTH_SECRET shorter than 32 characters must be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            app_env="development",
            database_url="postgresql+asyncpg://loyalty:secret@localhost:5432/poscenter",
            redis_url="redis://localhost:6379/0",
            jwt_signing_key="a" * 32,
            auth_challenge_hash_key="b" * 32,
            sms_otp_hash_key="d" * 32,
            whatsapp_login_number="+77001234567",
            wappi_login_profile_id="prod-profile-id",
            wappi_webhook_auth_header="X-Configured-Wappi-Header",
            wappi_webhook_auth_secret="short_secret",
            _env_file=None,
        )
    assert "WAPPI_WEBHOOK_AUTH_SECRET" in str(exc_info.value)


def test_config_dev_missing_wappi_webhook_auth_header_rejected() -> None:
    """WAPPI_WEBHOOK_AUTH_HEADER must not be empty."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            app_env="development",
            database_url="postgresql+asyncpg://loyalty:secret@localhost:5432/poscenter",
            redis_url="redis://localhost:6379/0",
            jwt_signing_key="a" * 32,
            auth_challenge_hash_key="b" * 32,
            sms_otp_hash_key="d" * 32,
            whatsapp_login_number="+77001234567",
            wappi_login_profile_id="prod-profile-id",
            wappi_webhook_auth_header="",
            wappi_webhook_auth_secret="c" * 32,
            _env_file=None,
        )
    assert "WAPPI_WEBHOOK_AUTH_HEADER" in str(exc_info.value)


def test_config_dev_omitted_wappi_webhook_auth_header_rejected() -> None:
    """WAPPI_WEBHOOK_AUTH_HEADER has no production default and omitting it must be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            app_env="development",
            database_url="postgresql+asyncpg://loyalty:secret@localhost:5432/poscenter",
            redis_url="redis://localhost:6379/0",
            jwt_signing_key="a" * 32,
            auth_challenge_hash_key="b" * 32,
            sms_otp_hash_key="d" * 32,
            whatsapp_login_number="+77001234567",
            wappi_login_profile_id="prod-profile-id",
            # wappi_webhook_auth_header is completely omitted!
            wappi_webhook_auth_secret="c" * 32,
            _env_file=None,
        )
    assert "WAPPI_WEBHOOK_AUTH_HEADER" in str(exc_info.value)


def test_config_test_mode_deterministic_test_header() -> None:
    """In test mode, WAPPI_WEBHOOK_AUTH_HEADER defaults deterministically to X-Test-Wappi-Auth."""
    cfg = Settings(
        app_env="test",
        database_url="sqlite+aiosqlite:///:memory:",
        _env_file=None,
    )
    assert cfg.wappi_webhook_auth_header == "X-Test-Wappi-Auth"


def test_no_hardcoded_x_wappi_secret_as_field_default() -> None:
    """Regression check: wappi_webhook_auth_header must have empty string default."""
    assert Settings.model_fields["wappi_webhook_auth_header"].default == ""


def test_config_dev_without_sms_otp_hash_key_rejected() -> None:
    """In development, missing SMS_OTP_HASH_KEY must be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            app_env="development",
            database_url="postgresql+asyncpg://loyalty:secret@localhost:5432/poscenter",
            redis_url="redis://localhost:6379/0",
            jwt_signing_key="a" * 32,
            auth_challenge_hash_key="b" * 32,
            sms_otp_hash_key="",
            whatsapp_login_number="+77001234567",
            wappi_login_profile_id="prod-profile-id",
            wappi_webhook_auth_header="X-Header",
            wappi_webhook_auth_secret="c" * 32,
            _env_file=None,
        )
    assert "SMS_OTP_HASH_KEY" in str(exc_info.value)


def test_config_prod_without_sms_otp_hash_key_rejected() -> None:
    """In production, missing SMS_OTP_HASH_KEY must be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            app_env="production",
            database_url="postgresql+asyncpg://loyalty:secret@localhost:5432/poscenter",
            redis_url="redis://localhost:6379/0",
            jwt_signing_key="a" * 32,
            auth_challenge_hash_key="b" * 32,
            sms_otp_hash_key="",
            whatsapp_login_number="+77001234567",
            wappi_login_profile_id="prod-profile-id",
            wappi_webhook_auth_header="X-Header",
            wappi_webhook_auth_secret="c" * 32,
            _env_file=None,
        )
    assert "SMS_OTP_HASH_KEY" in str(exc_info.value)


def test_config_dev_short_sms_otp_hash_key_rejected() -> None:
    """SMS_OTP_HASH_KEY shorter than 32 characters must be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            app_env="development",
            database_url="postgresql+asyncpg://loyalty:secret@localhost:5432/poscenter",
            redis_url="redis://localhost:6379/0",
            jwt_signing_key="a" * 32,
            auth_challenge_hash_key="b" * 32,
            sms_otp_hash_key="short_sms_key",
            whatsapp_login_number="+77001234567",
            wappi_login_profile_id="prod-profile-id",
            wappi_webhook_auth_header="X-Header",
            wappi_webhook_auth_secret="c" * 32,
            _env_file=None,
        )
    assert "SMS_OTP_HASH_KEY" in str(exc_info.value)


def test_config_auth_challenge_key_does_not_substitute_sms_key() -> None:
    """AUTH_CHALLENGE_HASH_KEY set and SMS_OTP_HASH_KEY missing must still be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            app_env="development",
            database_url="postgresql+asyncpg://loyalty:secret@localhost:5432/poscenter",
            redis_url="redis://localhost:6379/0",
            jwt_signing_key="a" * 32,
            auth_challenge_hash_key="b" * 32,
            # sms_otp_hash_key is omitted!
            whatsapp_login_number="+77001234567",
            wappi_login_profile_id="prod-profile-id",
            wappi_webhook_auth_header="X-Header",
            wappi_webhook_auth_secret="c" * 32,
            _env_file=None,
        )
    assert "SMS_OTP_HASH_KEY" in str(exc_info.value)


def test_config_dev_fake_provider_rejected() -> None:
    """SMS_PROVIDER_MODE=fake in development must fail-fast with ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            app_env="development",
            database_url="postgresql+asyncpg://loyalty:secret@localhost:5432/poscenter",
            redis_url="redis://localhost:6379/0",
            jwt_signing_key="a" * 32,
            auth_challenge_hash_key="b" * 32,
            sms_otp_hash_key="s" * 32,
            sms_provider_mode="fake",
            whatsapp_login_number="+77001234567",
            wappi_login_profile_id="prod-profile-id",
            wappi_webhook_auth_header="X-Header",
            wappi_webhook_auth_secret="c" * 32,
            _env_file=None,
        )
    assert "SMS_PROVIDER_MODE 'fake' is strictly forbidden in development/production" in str(exc_info.value)


def test_config_prod_fake_provider_rejected() -> None:
    """SMS_PROVIDER_MODE=fake in production must fail-fast with ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            app_env="production",
            database_url="postgresql+asyncpg://loyalty:secret@localhost:5432/poscenter",
            redis_url="redis://localhost:6379/0",
            jwt_signing_key="a" * 32,
            auth_challenge_hash_key="b" * 32,
            sms_otp_hash_key="s" * 32,
            sms_provider_mode="fake",
            whatsapp_login_number="+77001234567",
            wappi_login_profile_id="prod-profile-id",
            wappi_webhook_auth_header="X-Header",
            wappi_webhook_auth_secret="c" * 32,
            _env_file=None,
        )
    assert "SMS_PROVIDER_MODE 'fake' is strictly forbidden in development/production" in str(exc_info.value)


def test_config_test_fake_provider_allowed() -> None:
    """SMS_PROVIDER_MODE=fake is permitted when APP_ENV=test."""
    cfg = Settings(
        app_env="test",
        database_url="sqlite+aiosqlite:///:memory:",
        sms_provider_mode="fake",
        _env_file=None,
    )
    assert cfg.sms_provider_mode == "fake"


def test_config_unknown_provider_mode_rejected() -> None:
    """Unknown SMS_PROVIDER_MODE must be rejected with ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            app_env="test",
            database_url="sqlite+aiosqlite:///:memory:",
            sms_provider_mode="unknown_vendor",
            _env_file=None,
        )
    assert "Invalid SMS_PROVIDER_MODE 'unknown_vendor'" in str(exc_info.value)


