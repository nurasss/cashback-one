# POSCENTER Loyalty Cloud - Production Deployment Guide

## 1. Overview & Architecture

The POSCENTER Loyalty Cloud system is containerized and organized as follows:

```
                      +-----------------------------+
                      |   Client / Browser / Agent  |
                      +--------------+--------------+
                                     |
                                     v HTTPS (Port 443 / External TLS)
                      +-----------------------------+
                      |       Nginx Reverse Proxy   |
                      |   (Security Headers & SPA)  |
                      +--------------+--------------+
                                     |
                     +---------------+---------------+
                     |                               |
                     v (Static SPA)                  v (API & Webhooks)
        +-------------------------+     +-------------------------+
        |     Admin React SPA     |     |     FastAPI Backend     |
        |   (/usr/share/nginx)    |     |      (Uvicorn ASGI)     |
        +-------------------------+     +------------+------------+
                                                     |
                                   +-----------------+-----------------+
                                   |                                   |
                                   v                                   v
                      +-------------------------+         +-------------------------+
                      |   PostgreSQL 16 Engine  |         |      Redis 7 Store      |
                      |  (AsyncPG / Connection) |         | (Rate Limiting / Token) |
                      +-------------------------+         +-------------------------+
```

### Components
1. **Nginx Reverse Proxy**:
   - **Authoritative Model A TLS**: Nginx terminates TLS at the container edge (or serves as front proxy behind enterprise ingress). Under Model A, Nginx sets `proxy_set_header X-Forwarded-Proto $scheme;` authoritatively, preventing client-injected spoofed `X-Forwarded-Proto` headers from reaching backend services.
   - **Deterministic Admin SPA vs API Routing**: Uses two independent maps (`$is_admin_api` from `X-Admin-Request: 1`, `$accepts_html` from `Accept: text/html`) combined into `$is_spa_route`. The `X-Admin-Request: 1` header has absolute precedence and always proxies to the backend API. Direct browser navigations requesting HTML rewrite internally to `/index.html last`.
   - **Privacy-Preserving JSON Logs**: Access logs record request method, host, response code, timing, and client IP, but completely omit `$uri`, `$request_uri`, `$args`, `$query_string`, and `$http_referer` to prevent query string/credential leakage.
   - Serves React Admin SPA static assets with immutable cache headers and complete HTTP security headers (CSP, HSTS, X-Content-Type-Options, Referrer-Policy, Permissions-Policy).
2. **FastAPI Backend (Uvicorn)**:
   - Python 3.11+ / 3.14 async runtime.
   - **Single Proxy Trust**: Trusted proxy IPs are strictly defined via `FORWARDED_ALLOW_IPS` matching the exact internal reverse proxy IP (`172.28.0.10` in smoke stack) and passed directly via Uvicorn CLI `--forwarded-allow-ips`. Broad CIDRs (`10.0.0.0/8`, `0.0.0.0/0`) are rejected.
   - **Framework Route Template Logging**: Emits structured JSON logs containing normalized framework route templates (`route`, e.g. `/admin/cards/{card_id}`), never raw request paths containing customer IDs or query parameters. 404/unmatched routes log `"<unmatched>"`.
   - **Production Exception Logging Hygiene**: In production, unhandled 500 exceptions emit `event="unhandled_request_exception"` with `exc_info=False`, logging only `request_id`, `route`, and `exception_class`. Traceback, raw exception messages, SQL parameters, and potential secrets are completely suppressed from production log sinks.
   - Enforces strict startup configuration validation.
   - Manages connection pool to PostgreSQL with timeouts and pre-ping.
3. **PostgreSQL 16**:
   - Primary ACID datastore with strict constraints and Alembic migrations.
4. **Redis 7**:
   - In-memory cache for distributed rate-limiting and challenge token revocation.

---

## 2. Mandatory Disclaimers & Non-Goals

> [!WARNING]
> The following system boundaries and verification statuses are strictly documented:
> - **Real SMS adapter = NOT IMPLEMENTED**: Only `SMS_PROVIDER_MODE=disabled` is currently supported in production. The SMS fallback provider for OTP is not implemented; WhatsApp via Wappi is the primary customer auth channel.
> - **Real ONE / TASK-009B = DEFERRED**: POSCENTER ONE COM integration and live catalog mapping are deferred pending Stage0 hardware validation.
> - **Production TLS deployment = NOT VERIFIED/NOT DEPLOYED**: Local production-like smoke testing runs over internal HTTP on port 8080. Production TLS certificates, DNS management, and ingress termination must be configured by infrastructure operators.
> - **SLA 99% = NOT VERIFIED**: High-availability SLAs have not been verified through multi-node failover testing.
> - **p95 <= 500 ms = NOT VERIFIED**: Formal load testing across peak transactional volumes has not been completed.

---

## 3. Configuration & Environment Constraints

In `APP_ENV=production`, the application strictly enforces:
- `APP_ENV`: Must be strictly `production` (case-insensitive, whitespace trimmed; aliases like `prod` or `production2` are rejected).
- `DEBUG`: Must be `false`.
- `DATABASE_URL`: Must connect to PostgreSQL via `postgresql+asyncpg://` or `postgresql://`. SQLite is strictly rejected.
- `JWT_SIGNING_KEY`: Minimum 32 characters, non-default cryptographic secret.
- `ADMIN_JWT_SIGNING_KEY`: Minimum 32 characters, distinct from `JWT_SIGNING_KEY`.
- `AUTH_CHALLENGE_HASH_KEY`: Minimum 32 characters.
- `SMS_OTP_HASH_KEY`: Minimum 32 characters.
- `WAPPI_WEBHOOK_AUTH_SECRET`: Minimum 32 characters.
- `ADMIN_ALLOWED_ORIGINS`: Exact HTTPS origins only (no HTTP without dev opt-in; no wildcards).
- `ADMIN_ALLOW_INSECURE_HTTP`: Strictly `false` in production.
- `FORWARDED_ALLOW_IPS`: Explicit trusted CIDR/IP list. Wildcard `*` and broad zero-prefix networks (`0.0.0.0/0`, `::/0`) are rejected.
- `SMS_PROVIDER_MODE`: Must be `disabled`. Value `fake` is rejected.

---

## 4. Production Smoke Verification

A production-like smoke stack is provided in `deploy/compose.prod-smoke.yml`:

```bash
# 1. Generate strong ephemeral secrets (writes gitignored .env.prod-smoke)
python3 scripts/generate_prod_smoke_env.py

# 2. Launch the containerized smoke stack
docker compose -f deploy/compose.prod-smoke.yml --env-file .env.prod-smoke up --build -d

# 3. Check readiness and health
curl -f http://127.0.0.1:8080/health/live
curl -f http://127.0.0.1:8080/health/ready

# 4. Clean up smoke environment when done
docker compose -f deploy/compose.prod-smoke.yml --env-file .env.prod-smoke down -v
```

