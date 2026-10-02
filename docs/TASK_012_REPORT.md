# TASK-012 Technical Report: Production Runtime & Deployment Baseline

**Project:** POSCENTER Loyalty Cloud  
**Role:** Senior DevOps / Backend / Security Engineer  
**Baseline Branch:** `task-011b-fix-c`  
**Baseline Commit:** `02751b6565ce8fc84858ff1d4ba7c5bc99f42cca`  
**Current Branch:** `task-012-production-runtime`  
**Date:** 2026-10-03  

---

## 1. Executive Summary

TASK-012 establishes the complete production runtime, deployment configuration, and operational baseline for the Cloud components of the POSCENTER Loyalty system:
- **FastAPI Cloud Backend** (Python 3.11+, connection pooling, timeout safety, fail-closed configuration)
- **PostgreSQL 16 & Redis 7** (multi-stage health probes, transactional DDL Alembic migrations, connection resilience)
- **Admin Console SPA** (Vite + React 19, multi-stage static asset containerization, dual root/prefix routing)
- **Nginx Reverse Proxy** (1MB payload cap, bounded timeouts, modern CSP/security headers, request correlation forwarding, SPA fallback with strict JSON 404 API isolation)
- **Automated Backup & Disaster Recovery** (custom compressed `pg_dump -Fc` snapshots, SHA-256 integrity validation, mode `0600` permission enforcement, automated restore runbook)
- **Production Smoke Verification & CI/CD Pipeline** (`scripts/prod_smoke_check.sh`, `backend/tests/test_production_runtime.py`, `.github/workflows/ci.yml`)

### Mandatory Architectural Statements
> [!IMPORTANT]
> **SLA STATEMENT:** `SLA = NOT VERIFIED IN PRODUCTION`  
> Baseline configuration, pooling, timeouts, and health probes have been verified in containerized and local integration environments. Production-grade SLA verification under live multi-tenant traffic loads has not yet been executed against cloud infrastructure.

> [!NOTE]
> **BOUNDARY STATEMENT:** `TASK-009B = DEFERRED`  
> Stage 0 POSCENTER ONE discovery and hardware mapping remain deferred. No POSCENTER ONE boundaries, COM interfaces, or agent-to-ONE low-level integrations were modified or implemented.

---

## 2. Architecture & Components

```mermaid
flowchart TD
    Client["Browser / Agent / Customer App"] --> Proxy["Nginx Reverse Proxy (:80 / :8080)"]
    
    subgraph "DMZ & Routing Layer"
        Proxy -- "GET /index.html & static /assets/*" --> StaticSPA["Admin SPA Static Files"]
        Proxy -- "X-Request-ID & API routes" --> Backend["FastAPI Backend (:8000)"]
    end

    subgraph "Backend Core Services"
        Backend --> Pool["SQLAlchemy Connection Pool"]
        Backend --> Limiter["Redis Rate Limiter"]
        Pool --> Postgres[("PostgreSQL 16 (poscenter_loyalty)")]
        Limiter --> Redis[("Redis 7 (cache & limits)")]
    end

    subgraph "Health & Readiness Monitoring"
        Liveness["/health/live (Process only)"]
        Readiness["/health/ready (Postgres + Redis + Alembic 0009)"]
    end
```

### 2.1 Fail-Closed Configuration (`backend/app/core/config.py`)
- **Strict PostgreSQL Requirement:** Rejects SQLite in both `development` and `production` environments.
- **Secret Entropy & Weak Key Detection:** Prevents execution if any JWT or HMAC secret (`jwt_signing_key`, `admin_jwt_signing_key`, `auth_challenge_hash_key`, `sms_otp_hash_key`, `wappi_webhook_auth_secret`) is shorter than 32 characters or contains default/placeholder values (`changeme`, `secret`, `password`, `test_`, `fixture`, `default`).
- **Transport Security:** Forbids `ADMIN_ALLOW_INSECURE_HTTP=true` in production; mandates explicit HTTPS URLs in `ADMIN_ALLOWED_ORIGINS`.
- **Proxy Header Trust:** Prohibits wildcard trust (`FORWARDED_ALLOW_IPS=*`) in production; defaults to local/private CIDR blocks.
- **Provider Integrity:** Rejects `SMS_PROVIDER_MODE=fake` outside of test mode.

### 2.2 Connection Pooling & Timeouts (`backend/app/db/session.py`, `backend/app/services/rate_limiter.py`)
- **Database Engine Pool:** Configurable bounded connection pooling (`pool_size=10`, `max_overflow=5`, `pool_timeout=10s`, `pool_recycle=1800s`, `pool_pre_ping=true`).
- **Query Protection:** Configurable `statement_timeout` set to 15,000ms on PostgreSQL connections.
- **Redis Resilience:** Explicit `socket_connect_timeout=3s` and `socket_timeout=3s` on Redis async clients.

### 2.3 Health & Readiness Probes (`backend/app/api/health.py`)
- **Liveness Probe (`/health/live`):** Returns HTTP 200 `{"status": "ok"}` based strictly on process health. Does not check database or Redis, preventing cascading pod restarts during downstream blips.
- **Readiness Probe (`/health/ready`):** Deep health verification:
  1. Checks active database query execution (`SELECT 1`).
  2. Verifies Alembic schema revision matches `0009_admin_mutations`.
  3. Pings Redis cluster/standalone instance.
  4. Returns HTTP 503 Service Unavailable if any component is degraded or unmigrated, with zero disclosure of database URLs or credentials.

### 2.4 Structured Logging & Redaction (`backend/app/core/logging.py`)
- **JSON Formatting:** Structured JSON logging in production with ISO 8601 UTC timestamps, log level, and logger name.
- **Request Correlation:** `RequestCorrelationMiddleware` extracts valid incoming `X-Request-ID` or generates UUID4, propagates it in response headers, and attaches it to request context.
- **Automated Redaction:** Redacts credentials from database URLs (`postgresql://[REDACTED]:[REDACTED]@...`), agent keys (`agk_...`), refresh tokens (`rfr_...`, `adm_rfr_...`), and Bearer tokens. Query parameters are stripped from access logs.

### 2.5 Reverse Proxy & Routing Isolation (`deploy/nginx/`)
- **Security Headers:** Strict CSP, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy`.
- **Client Body Limit:** Bounded to `1M`.
- **SPA & API Dual Routing:**
  - Browser visits and refreshes on `/` or `/admin/*` with `Accept: text/html` serve the React SPA `index.html`.
  - API calls to `/health`, `/agent`, `/auth`, `/me`, `/webhooks`, and `/admin` proxy to backend upstream.
  - Unknown API routes return HTTP 404 JSON from FastAPI, never falling back to HTML.

---

## 3. Operational Tooling & Containerization

| File | Purpose |
|---|---|
| `backend/Dockerfile` | Multi-stage build, non-root `appuser` (UID 10001), healthcheck |
| `admin/Dockerfile` | Multi-stage build (Node 20 Vite builder -> Nginx 1.27 runner) |
| `.dockerignore` | Exclusion of `.venv`, `node_modules`, `.env*`, `.git`, temporary artifacts |
| `deploy/compose.prod-smoke.yml` | Full containerized stack (postgres, redis, migration, backend, proxy) |
| `.env.prod-smoke.example` | Production-like smoke environment configuration template |
| `scripts/backup_postgres.sh` | Automated `pg_dump -Fc` with SHA-256 checksum and mode `0600` |
| `scripts/restore_postgres.sh` | Fail-closed restore with checksum verification and overwrite guard |
| `docs/BACKUP_RESTORE.md` | Runbook for backup scheduling, systemd timers, and disaster recovery |
| `scripts/prod_smoke_check.sh` | Automated smoke script validating probes, routing, and API isolation |
| `.github/workflows/ci.yml` | GitHub Actions CI workflow covering all component gates |

---

## 4. Verification & Quality Gates

### 4.1 Pytest Test Suite
- Non-Postgres Unit & Integration Tests: **233 passed** (including 18 new production runtime tests in `backend/tests/test_production_runtime.py`).
- PostgreSQL Concurrency Suite: All Stage 1-4 tests verified against PostgreSQL 16.

### 4.2 Static Analysis & Bytecode Compilation
- `ruff check .` -> PASSED (0 errors).
- `mypy .` -> PASSED (strict mode, 0 errors).
- `python -m compileall app migrations tests` -> PASSED (0 compilation errors).

### 4.3 Admin Console SPA
- `npm test` -> PASSED (6 test files, 44 tests passed).
- `npm run typecheck` -> PASSED.
- `npm run lint` -> PASSED.
- `npm run build` -> PASSED.
