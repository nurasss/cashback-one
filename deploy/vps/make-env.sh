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
# Media & FTPS hosting storage (optional, for image uploads)
MEDIA_FTPS_HOST=
MEDIA_FTPS_PORT=21
MEDIA_FTPS_USER=
MEDIA_FTPS_PASSWORD=
MEDIA_FTPS_ROOT_DIR=
MEDIA_PUBLIC_BASE_URL=https://cashback-qr.poscenter.kz/media
MEDIA_MAX_UPLOAD_BYTES=10485760
# Apple Wallet / Google Wallet passes (optional, uncomment when keys are available)
# WALLET_PUBLIC_BASE_URL=https://api.cashback-qr.poscenter.kz
# WALLET_ORGANIZATION_NAME="POSCENTER ONE"
# WALLET_LINK_TTL_SECONDS=600
# APPLE_PASS_TYPE_ID=pass.kz.poscenter.cashback
# APPLE_TEAM_ID=XXXXXXXXXX
# APPLE_PASS_CERT_FILE=/app/secrets/apple_pass_cert.pem
# APPLE_PASS_KEY_FILE=/app/secrets/apple_pass_key.pem
# APPLE_PASS_KEY_PASSWORD=
# APPLE_WWDR_CERT_FILE=/app/secrets/apple_wwdr.pem
# GOOGLE_WALLET_ISSUER_ID=3388000000022xxxxxx
# GOOGLE_WALLET_SERVICE_ACCOUNT_FILE=/app/secrets/google_sa.json
ENV
chmod 600 .env
echo ".env created (permissions 600); secrets are not printed"
