# TASK-012-FIX-A Delivery Report: Production Runtime & Deployment Baseline Hardening

## Executive Summary
This report documents the resolution of all blocking findings identified in the independent review of **TASK-012** (Production Runtime & Deployment Baseline). All modifications were implemented on branch `task-012-fix-a` branched from baseline `29db4ea08890d0ad3d77692855ed50e120d19831`.

---

## Mandatory Scope & Status Statements

> [!IMPORTANT]
> The following project statuses are strictly documented:
> - **Real SMS adapter = NOT IMPLEMENTED**: Only `SMS_PROVIDER_MODE=disabled` is supported. Customer authentication is conducted via WhatsApp (Wappi).
> - **Real ONE / TASK-009B = DEFERRED**: Real POSCENTER ONE database discovery and live catalog integration are deferred pending on-premise hardware validation.
> - **Production TLS deployment = NOT VERIFIED/NOT DEPLOYED**: Smoke verification uses local HTTP on port 8080. Production TLS certificates, reverse proxy DNS, and edge termination must be managed by production infrastructure.
> - **SLA 99% = NOT VERIFIED**: High-availability clustering and automated failover have not been verified.
> - **p95 <= 500 ms = NOT VERIFIED**: Latency benchmarks under peak load are unverified.

---

## Detailed Remediation Summary

### 1. APP_ENV P0 Normalization & Strict Validation
- Added `@field_validator("app_env", mode="before")` in `backend/app/core/config.py`:
  - Strips leading and trailing whitespace.
  - Lowercases the value.
  - Strictly accepts only canonical set: `{"test", "development", "production"}`.
  - Rejects aliases (`prod`, `dev`, `stage`, `production2`) with clear `ValueError`.
- Enforces all production security constraints against the canonical string: SQLite forbidden, `DEBUG=false`, strong secrets required, fake SMS forbidden, insecure HTTP cookies forbidden.

### 2. LOGGING P0 Hardening & Redaction
- Overhauled `backend/app/core/logging.py`:
  - `redact_sensitive_text`: Redacts password, OTP, JWT, Agent API keys (`agk_`), Agent key hashes, DATABASE_URL credentials, Redis credentials, ONE connection string passwords (`Password=...`), E.164/CIS phone numbers, barcodes (12-14 digits), full names, and sensitive headers (`Authorization`, `Cookie`, `X-Agent-Key`).
  - `safe_route_path`: Masks path parameters containing UUIDs, phone numbers, barcodes, and numeric IDs to prevent PII leakage in access logs.
  - Suppressed default `uvicorn.access` loggers in production to prevent logging raw queries and referrers.
  - Updated `deploy/nginx/nginx.conf`: replaced `$request_uri` with `$uri` (dropping raw query strings) and removed `$http_referer`.
  - Updated `backend/app/core/errors.py`: logged unhandled exceptions using `exc.__class__.__name__` and `safe_route_path` without raw traceback leakage or user PII.

### 3. COMPOSE PROD-SMOKE Configuration
- Fixed `deploy/compose.prod-smoke.yml` and `.env.prod-smoke.example`:
  - Replaced phantom environment names (`CUSTOMER_JWT_SECRET`, `ADMIN_JWT_SECRET`, `WAPPI_PROFILE_ID`) with real `Settings` fields: `JWT_SIGNING_KEY`, `ADMIN_JWT_SIGNING_KEY`, `AUTH_CHALLENGE_HASH_KEY`, `SMS_OTP_HASH_KEY`, `WHATSAPP_LOGIN_NUMBER`, `WAPPI_LOGIN_PROFILE_ID`, `WAPPI_WEBHOOK_AUTH_HEADER`, `WAPPI_WEBHOOK_AUTH_SECRET`.
  - Added full environment variables to the `migration` container to prevent `Settings()` validation crashes during Alembic boots.
  - Explicitly set `SMS_PROVIDER_MODE=disabled`.
  - Mounted `security_headers.conf` in the proxy service.

### 4. PROXY TRUST & IP/CIDR Validation
- In `backend/app/core/config.py`, parsed every item in `FORWARDED_ALLOW_IPS` using Python's `ipaddress` module.
- Strictly rejects `*`, `0.0.0.0/0`, `::/0`, any broad network with `prefixlen == 0` (e.g. `127.0.0.1,0.0.0.0/0`), empty strings, or invalid IP/CIDR syntax.

### 5. ADMIN SPA Routing in Nginx
- In `deploy/nginx/default.conf`, created a combined map `$is_spa_page_request` based on `$http_accept` and `$http_x_admin_request`.
- Browser navigations to `/admin/*` (`Accept: text/html` without `X-Admin-Request`) rewrite to `/index.html last` to serve the React SPA from disk.
- API and mutation calls (`Accept: application/json` or `X-Admin-Request: 1`) proxy to backend.
- Non-existent backend endpoints return backend 404 JSON, not `index.html`.

### 6. HTTPS Trust Chain & Header Forwarding
- In `deploy/nginx/default.conf`:
  - Added map `$http_x_forwarded_proto $pass_proto` to preserve incoming `https` schemes from TLS terminators.
  - Set `proxy_set_header X-Forwarded-Proto $pass_proto;`.
- In `backend/app/services/admin_security.py`:
  - Implemented `is_trusted_proxy_client(ip)` and `get_effective_scheme(request)`.
  - Requests from untrusted peer IPs cannot spoof `X-Forwarded-Proto` (the header is ignored).
  - Production admin session cookies enforce `secure=True`.

### 7. PostgreSQL Restore Script Fail-Closed Hardening
- In `scripts/restore_postgres.sh`:
  - Pre-restore connectivity check: runs `psql -c "SELECT 1;"` against target database before starting.
  - Captures `pg_restore` exit code and aborts if `exit_code > 1` (fatal errors).
  - Post-restore database check: verifies database connectivity and validates that `alembic_version` exists and contains a non-empty revision.
  - Exits with non-zero status code on any failure.
  - Verified with forced failure test (`PGHOST=/tmp PGPORT=1`).

### 8. Backend Packaging & Build Context
- In `backend/pyproject.toml`:
  - Added `[build-system]` (`requires = ["setuptools>=61.0"]`, `build-backend = "setuptools.build_meta"`).
  - Added `[tool.setuptools.packages.find]` (`include = ["app*"]`, `exclude = ["migrations*", "tests*"]`).
  - Added `sqlalchemy[asyncio]>=2.0.30` (includes `greenlet`).
  - Added `backend/README.md`.
- Added `backend/.dockerignore` and `admin/.dockerignore` to avoid copying `.git`, `.venv`, caches, and build artifacts into Docker build contexts.

### 9. Static Security Headers
- Created `deploy/nginx/security_headers.conf` with CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, and Permissions-Policy.
- Included `security_headers.conf` in both the server block and the static asset cache location to ensure caching directives do not wipe security headers.

---

## Verification & Quality Gates

| Check | Command | Status |
|---|---|---|
| Backend Pytest (unit/smoke) | `pytest backend/tests/ -k "not postgres"` | PASSED (251 passed, 37 deselected) |
| Production Runtime Regression Tests | `pytest backend/tests/test_production_runtime.py` | PASSED (36 passed) |
| Restore Script Forced Failure | `PGHOST=/tmp PGPORT=1 ./scripts/restore_postgres.sh ...` | PASSED (exits 1 on error) |
| Git Status | `git status` | Clean working tree on branch `task-012-fix-a` |
