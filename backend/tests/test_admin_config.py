import pytest
from pydantic import ValidationError

from app.core.config import Settings


def valid_settings(**override: object) -> dict[str, object]:
    result: dict[str, object] = {
        "app_env": "development",
        "database_url": "postgresql+asyncpg://fixture:fixture@db.example.invalid/fixture",
        "redis_url": "redis://cache.example.invalid/0",
        "jwt_signing_key": "customer-fixture-key-0123456789abcdef",
        "auth_challenge_hash_key": "fixture-challenge-key-0123456789abcdef",
        "sms_otp_hash_key": "fixture-otp-hash-key-0123456789abcdef",
        "whatsapp_login_number": "+77001234567",
        "wappi_login_profile_id": "fixture-profile",
        "wappi_webhook_auth_header": "X-Fixture-Auth",
        "wappi_webhook_auth_secret": "fixture-wappi-key-0123456789abcdef",
        "admin_jwt_signing_key": "separate-admin-key-0123456789abcdef",
        "admin_allowed_origins": ["https://admin.example.invalid"],
        "_env_file": None,
    }
    result.update(override)
    return result


def test_admin_jwt_key_is_required_and_independent_of_customer_jwt() -> None:
    with pytest.raises(ValidationError, match="ADMIN_JWT_SIGNING_KEY"):
        Settings(**valid_settings(admin_jwt_signing_key=""))
    with pytest.raises(ValidationError, match="different"):
        Settings(**valid_settings(admin_jwt_signing_key="customer-fixture-key-0123456789abcdef"))


def test_production_requires_exact_https_browser_origins() -> None:
    with pytest.raises(ValidationError, match="HTTP admin origins"):
        Settings(**valid_settings(
            app_env="production", admin_allowed_origins=["http://localhost:5173"], admin_allow_insecure_http=True
        ))
    for origin in ["*", "https://admin.example.invalid/path", "https://login:password@example.invalid"]:
        with pytest.raises(ValidationError):
            Settings(**valid_settings(admin_allowed_origins=[origin]))


def test_dev_http_browser_origin_requires_explicit_opt_in() -> None:
    with pytest.raises(ValidationError, match="HTTP admin origins"):
        Settings(**valid_settings(admin_allowed_origins=["http://localhost:5173"]))
    config = Settings(**valid_settings(
        admin_allowed_origins=["http://localhost:5173"], admin_allow_insecure_http=True
    ))
    assert config.admin_allowed_origins == ["http://localhost:5173"]
