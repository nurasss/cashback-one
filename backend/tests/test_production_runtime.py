import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.config import Settings
from app.core.logging import redact_sensitive_text


def _build_valid_prod_kwargs() -> dict[str, str | bool | list[str]]:
    return {
        "app_env": "production",
        "debug": False,
        "database_url": "postgresql+asyncpg://poscenter_app:prod_db_pass_928374189234@127.0.0.1:5432/poscenter_loyalty",
        "redis_url": "redis://127.0.0.1:6379/0",
        "jwt_signing_key": "9f8e7d6c5b4a3928172635485960718293a4b5c6d7e8f90123456789abcdef01",
        "admin_jwt_signing_key": "1234567890abcdef0123456789abcdef9f8e7d6c5b4a39281726354859607182",
        "auth_challenge_hash_key": "aabbccddeeff00112233445566778899aabbccddeeff00112233445566778899",
        "sms_otp_hash_key": "11223344556677889900aabbccddeeff11223344556677889900aabbccddeeff",
        "whatsapp_login_number": "+77001234567",
        "wappi_login_profile_id": "profile_prod_12345",
        "wappi_webhook_auth_header": "X-Wappi-Webhook-Signature",
        "wappi_webhook_auth_secret": "99887766554433221100ffeeddccbbaa99887766554433221100ffeeddccbbaa",
        "admin_allowed_origins": ["https://admin.loyalty.local", "https://loyalty.local"],
        "admin_allow_insecure_http": False,
        "sms_provider_mode": "disabled",
        "forwarded_allow_ips": "127.0.0.1,10.0.0.0/8",
    }


def test_production_config_valid() -> None:
    settings = Settings(**_build_valid_prod_kwargs())
    assert settings.app_env == "production"
    assert settings.debug is False
    assert settings.admin_allow_insecure_http is False


def test_production_config_rejects_sqlite() -> None:
    kwargs = _build_valid_prod_kwargs()
    kwargs["database_url"] = "sqlite+aiosqlite:////tmp/test.db"
    with pytest.raises(ValueError, match="DATABASE_URL must not use SQLite in production"):
        Settings(**kwargs)


def test_production_config_rejects_debug_enabled() -> None:
    kwargs = _build_valid_prod_kwargs()
    kwargs["debug"] = True
    with pytest.raises(ValueError, match="DEBUG must be disabled"):
        Settings(**kwargs)


def test_production_config_rejects_weak_customer_jwt_secret() -> None:
    kwargs = _build_valid_prod_kwargs()
    kwargs["jwt_signing_key"] = "changeme-default-key-32-chars-minimum"
    with pytest.raises(ValueError, match="JWT_SIGNING_KEY uses an insecure or default secret"):
        Settings(**kwargs)


def test_production_config_rejects_weak_admin_jwt_secret() -> None:
    kwargs = _build_valid_prod_kwargs()
    kwargs["admin_jwt_signing_key"] = "changeme-admin-jwt-key-32-chars-minimum"
    with pytest.raises(ValueError, match="ADMIN_JWT_SIGNING_KEY uses an insecure or default secret"):
        Settings(**kwargs)


def test_production_config_rejects_insecure_admin_http() -> None:
    kwargs = _build_valid_prod_kwargs()
    kwargs["admin_allow_insecure_http"] = True
    with pytest.raises(ValueError, match="ADMIN_ALLOW_INSECURE_HTTP is strictly forbidden"):
        Settings(**kwargs)


def test_production_config_rejects_non_https_admin_origin() -> None:
    kwargs = _build_valid_prod_kwargs()
    kwargs["admin_allowed_origins"] = ["http://admin.insecure.test"]
    with pytest.raises(ValueError, match="must use HTTPS in production"):
        Settings(**kwargs)


def test_production_config_rejects_wildcard_forwarded_allow_ips() -> None:
    kwargs = _build_valid_prod_kwargs()
    kwargs["forwarded_allow_ips"] = "*"
    with pytest.raises(ValueError, match="FORWARDED_ALLOW_IPS must not trust all IPs"):
        Settings(**kwargs)


def test_production_config_rejects_fake_sms_provider() -> None:
    kwargs = _build_valid_prod_kwargs()
    kwargs["sms_provider_mode"] = "fake"
    with pytest.raises(ValueError, match="SMS_PROVIDER_MODE 'fake' is strictly forbidden"):
        Settings(**kwargs)


@pytest.mark.asyncio
async def test_health_liveness_probe_returns_200(client: AsyncClient) -> None:
    response = await client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_health_readiness_probe_success(client: AsyncClient) -> None:
    with (
        patch("app.api.health.check_database_readiness", new=AsyncMock(return_value=(True, "ok"))),
        patch("app.api.health.check_redis_readiness", new=AsyncMock(return_value=(True, "ok"))),
    ):
        response = await client.get("/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["components"]["database"] == "ok"
        assert data["components"]["redis"] == "ok"


@pytest.mark.asyncio
async def test_health_readiness_probe_fails_on_db_down(client: AsyncClient) -> None:
    with (
        patch("app.api.health.check_database_readiness", new=AsyncMock(return_value=(False, "unavailable"))),
        patch("app.api.health.check_redis_readiness", new=AsyncMock(return_value=(True, "ok"))),
    ):
        response = await client.get("/health/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["components"]["database"] == "unavailable"
        # Must not leak connection strings or passwords
        assert "password" not in str(data).lower()
        assert "fixture" not in str(data).lower()


@pytest.mark.asyncio
async def test_health_readiness_probe_fails_on_redis_down(client: AsyncClient) -> None:
    with (
        patch("app.api.health.check_database_readiness", new=AsyncMock(return_value=(True, "ok"))),
        patch("app.api.health.check_redis_readiness", new=AsyncMock(return_value=(False, "unavailable"))),
    ):
        response = await client.get("/health/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["components"]["redis"] == "unavailable"


@pytest.mark.asyncio
async def test_health_readiness_probe_fails_on_migration_pending(client: AsyncClient) -> None:
    with (
        patch("app.api.health.check_database_readiness", new=AsyncMock(return_value=(False, "migration_pending"))),
        patch("app.api.health.check_redis_readiness", new=AsyncMock(return_value=(True, "ok"))),
    ):
        response = await client.get("/health/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["components"]["database"] == "migration_pending"


@pytest.mark.asyncio
async def test_request_id_middleware_preserves_valid_incoming_id(client: AsyncClient) -> None:
    req_id = "test-request-id-12345678"
    response = await client.get("/health/live", headers={"X-Request-ID": req_id})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == req_id


@pytest.mark.asyncio
async def test_request_id_middleware_generates_id_if_missing(client: AsyncClient) -> None:
    response = await client.get("/health/live")
    assert response.status_code == 200
    assigned_id = response.headers.get("X-Request-ID")
    assert assigned_id is not None
    # Verify it is a valid UUID
    uuid.UUID(assigned_id)


@pytest.mark.asyncio
async def test_request_id_middleware_replaces_malformed_id(client: AsyncClient) -> None:
    # Contains invalid characters/injection
    malformed_id = "bad id<script>alert(1)</script>"
    response = await client.get("/health/live", headers={"X-Request-ID": malformed_id})
    assert response.status_code == 200
    assigned_id = response.headers.get("X-Request-ID")
    assert assigned_id != malformed_id
    uuid.UUID(assigned_id)


def test_log_redaction_removes_sensitive_data() -> None:
    sample_text = (
        "Connecting to postgresql://dbuser:super_secret_password@db.example.com:5432/poscenter "
        "with agent key agk_live_test_1234567890abcdef and token rfr_refresh_secret_1234567890."
    )
    redacted = redact_sensitive_text(sample_text)
    assert "super_secret_password" not in redacted
    assert "agk_live_test_1234567890abcdef" not in redacted
    assert "rfr_refresh_secret_1234567890" not in redacted
    assert "[REDACTED]" in redacted
    assert "postgresql://[REDACTED]:[REDACTED]@db.example.com:5432/poscenter" in redacted
