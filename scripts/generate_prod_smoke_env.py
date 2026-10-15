#!/usr/bin/env python3
"""Generates a valid, cryptographically random ephemeral .env.prod-smoke file for local smoke testing."""

from pathlib import Path
import secrets


def generate_smoke_env(output_path: Path | None = None) -> Path:
    if output_path is None:
        output_path = Path(__file__).resolve().parent.parent / ".env.prod-smoke"

    pg_password = secrets.token_hex(16)
    jwt_key = secrets.token_hex(32)
    admin_jwt_key = secrets.token_hex(32)
    auth_hash_key = secrets.token_hex(32)
    sms_hash_key = secrets.token_hex(32)
    wappi_secret = secrets.token_hex(32)

    content = f"""# Auto-generated ephemeral smoke test environment
APP_ENV=production
DEBUG=false
APP_NAME=POSCENTER Loyalty
APP_VERSION=0.1.0
LOG_FORMAT=json
LOG_LEVEL=INFO
PORT=8080

POSTGRES_DB=poscenter_loyalty_smoke
POSTGRES_USER=poscenter_app
POSTGRES_PASSWORD={pg_password}
DATABASE_URL=postgresql+asyncpg://poscenter_app:{pg_password}@postgres:5432/poscenter_loyalty_smoke

DB_POOL_SIZE=10
DB_MAX_OVERFLOW=5
DB_POOL_TIMEOUT_SECONDS=10
DB_POOL_RECYCLE_SECONDS=1800
DB_POOL_PRE_PING=true
DB_STATEMENT_TIMEOUT_MS=15000

REDIS_URL=redis://redis:6379/0
REDIS_CONNECT_TIMEOUT_SECONDS=3
REDIS_SOCKET_TIMEOUT_SECONDS=3

JWT_SIGNING_KEY={jwt_key}
ADMIN_JWT_SIGNING_KEY={admin_jwt_key}
AUTH_CHALLENGE_HASH_KEY={auth_hash_key}
SMS_OTP_HASH_KEY={sms_hash_key}

ADMIN_ALLOWED_ORIGINS=["https://admin.loyalty.local","https://loyalty.local"]
ADMIN_ALLOW_INSECURE_HTTP=false
VITE_API_BASE_URL=https://loyalty.local
VITE_ALLOW_INSECURE_HTTP=0

FORWARDED_ALLOW_IPS=172.28.0.10

SMS_PROVIDER_MODE=disabled

WHATSAPP_LOGIN_NUMBER=+77001234567
WAPPI_LOGIN_PROFILE_ID=smoke-profile-123
WAPPI_WEBHOOK_AUTH_HEADER=X-Wappi-Webhook-Signature
WAPPI_WEBHOOK_AUTH_SECRET={wappi_secret}
"""
    output_path.write_text(content)
    output_path.chmod(0o600)
    return output_path


if __name__ == "__main__":
    out = generate_smoke_env()
    print(f"[SUCCESS] Generated ephemeral smoke environment at {out}")
