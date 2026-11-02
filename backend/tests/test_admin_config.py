from typing import Any

import pytest
from fastapi.middleware.cors import CORSMiddleware
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import app


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


def cors_kwargs() -> dict[str, Any]:
    middleware = next(item for item in app.user_middleware if item.cls is CORSMiddleware)
    return {**middleware.kwargs, "allow_origins": ["https://admin.test"]}


@pytest.mark.parametrize(
    ("method", "expected"),
    [("GET", 200), ("POST", 200), ("PATCH", 200), ("DELETE", 200), ("PUT", 400)],
)
@pytest.mark.asyncio
async def test_admin_preflight_allows_only_used_methods(method: str, expected: int) -> None:
    """The browser sends the admin DELETE only after this preflight succeeds."""
    transport = ASGITransport(app=CORSMiddleware(app, **cors_kwargs()))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/admin/promotions/00000000-0000-0000-0000-000000000000",
            headers={
                "Origin": "https://admin.test",
                "Access-Control-Request-Method": method,
                "Access-Control-Request-Headers": "authorization,content-type,x-admin-request",
            },
        )
    assert response.status_code == expected
