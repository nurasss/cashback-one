#!/usr/bin/env bash
# Generates /opt/cashback-one/.env with fresh random secrets. Refuses to overwrite an existing file.
set -euo pipefail
cd "$(dirname "$0")"
[ -e .env ] && { echo ".env already exists; refusing to overwrite" >&2; exit 1; }
r() { openssl rand -hex "${1:-32}"; }
umask 077
PGPASS="$(r 24)"
cat > .env <<ENV
POSTGRES_PASSWORD=${PGPASS}
APP_ENV=production
DEBUG=false
LOG_FORMAT=json
LOG_LEVEL=INFO
DATABASE_URL=postgresql+asyncpg://cashback:${PGPASS}@postgres:5432/cashback
REDIS_URL=redis://redis:6379/0
JWT_SIGNING_KEY=$(r 32)
ADMIN_JWT_SIGNING_KEY=$(r 32)
AUTH_CHALLENGE_HASH_KEY=$(r 32)
SMS_OTP_HASH_KEY=$(r 32)
ADMIN_ALLOWED_ORIGINS=["https://cashback-qr.poscenter.kz"]
ADMIN_ALLOW_INSECURE_HTTP=false
SMS_PROVIDER_MODE=disabled
WHATSAPP_PROVIDER_MODE=disabled
WAPPI_API_TOKEN=
WHATSAPP_LOGIN_NUMBER=+77001234567
WAPPI_LOGIN_PROFILE_ID=not-configured
WAPPI_WEBHOOK_AUTH_HEADER=X-Wappi-Webhook-Signature
WAPPI_WEBHOOK_AUTH_SECRET=$(r 32)
FORWARDED_ALLOW_IPS=172.18.0.0/16
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=3
DB_POOL_TIMEOUT_SECONDS=10
DB_POOL_RECYCLE_SECONDS=1800
DB_POOL_PRE_PING=true
DB_STATEMENT_TIMEOUT_MS=15000
ENV
chmod 600 .env
echo ".env created (permissions 600); secrets are not printed"
