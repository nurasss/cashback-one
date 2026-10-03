# Pre-ONE End-to-End Integration Harness

## Executive Summary

The Pre-ONE End-to-End Integration Harness (`TASK-013`) establishes a deterministic, hermetic integration test gate verifying the complete real-infrastructure chain of POSCENTER Loyalty before connecting to physical 1C / POSCENTER ONE infrastructure.

---

## Architectural Chain

```
               [TestLoyaltySource] (In-memory DTOs, zero 1C assumptions)
                       │
                       ▼
             [Real AgentRuntime] (StateStore SQLite, ProcessLock, RetryState)
                       │
                       ▼ (HTTP POST /agent/heartbeat, /agent/sync/* with X-Agent-Key)
             [HttpCloudClient]
                       │
                       ▼ (HTTP loopback to real port)
             [Real Uvicorn ASGI Backend Process]
              ├── app.main:app
              ├── Request ID Middleware
              ├── Tenant Isolation Enforcer
              └── Zero-Credential Redacting Logger
                       │
         ┌─────────────┴─────────────┐
         ▼                           ▼
[Real PostgreSQL 16]          [Real Redis 7]
(All 9 Alembic Migrations)    (Sessions & Rate Limits)
         │
         ├───────────────────────────┐
         ▼                           ▼
[Customer-Facing API]         [Admin SPA API]
- /auth/challenge             - /admin/auth/login
- /webhooks/wappi             - /admin/businesses
- /me/cards (Auto-binding)    - /admin/agents
- /me/cards/{id}/transactions - /admin/dashboard
                              - /admin/agents/{id}/revoke
                              - /admin/agents/{id}/rotate-key
                              - /admin/agents/{id}/full-resync
```

---

## Critical Test-Double Boundaries & Disclaimers

### 1. In-Memory Source Boundary
- `TestLoyaltySource` is strictly confined to `e2e/source.py`.
- No mock or fake ONE adapter is registered or selectable in production code.
- No `APP_ENV=production` bypass, `/test/*` backdoor endpoint, or `DISABLE_AUTH` flag exists in application paths.

### 2. Explicit Unverified ONE Statuses
As established by Stage0 and preserved across all milestones:
```ini
REAL_WINDOWS_SERVICE = NOT VERIFIED
REAL_V83_COMCONNECTOR = NOT VERIFIED
REAL_ONE_CONNECTION = NOT VERIFIED
REAL_ONE_METADATA_DISCOVERY = NOT VERIFIED
REAL_ONE_MAPPING = NOT VERIFIED
```
Physical discovery of 1C COM interfaces and metadata schemas remains deferred to **TASK-009B**.

---

## Flow Verifications (18 Checkpoints)

1. **Admin HTTP Login**: Real HTTP `POST /admin/auth/login` issuing signed JWT access token and `admin_refresh` cookie.
2. **Business A Provisioning**: Superadmin creates Business A via `POST /admin/businesses`.
3. **Agent A Provisioning**: Superadmin generates Agent A via `POST /admin/agents` with one-time API key disclosure (`key_hash` never exposed).
4. **Agent Heartbeat**: Real HTTP heartbeat via `HttpCloudClient` updating agent `last_seen_at` in PostgreSQL.
5. **Card A & Transaction T1 Sync**: Synchronizes Card A with 13-digit barcode (`0123456789012` with preserved leading zero) and Transaction T1.
6. **Customer WhatsApp Reverse Login**: Challenge generation, simulated inbound Wappi webhook delivery with HMAC verification, and secure token exchange.
7. **Customer Wallet Auto-Binding**: Phone-based discovery auto-binds Card A into wallet, preserving 13-digit barcode and initial balance (`1000.0000`).
8. **Second Sync (Balance & History)**: Updates Card A balance (`1350.0000`) and appends Transaction T2 without server restart.
9. **Idempotency**: Re-running sync cycle causes zero duplicate cards or transactions.
10. **Multi-Tenant Isolation**: Business B and Agent B created; Agent A syncs are strictly partitioned from Business B, and Customer A cannot see Card B.
11. **Manager Tenant Isolation over HTTP**: Manager A sees only Business A agents/cards, cannot query other businesses, and receives 403 on `/admin/businesses`.
12. **Superadmin Aggregate Visibility**: Superadmin views both businesses, both agents, and aggregate metrics on `/admin/dashboard`.
13. **Durable Full-Resync**: Full-resync command registered with persistent status `pending` (execution deferred).
14. **Agent Revocation**: Revoked Agent B key is rejected with `401 Unauthorized`.
15. **Agent Key Rotation**: Old key rejected, rotated key accepted on heartbeat.
16. **Fault & Retry Safety**: Network transport failure halts sync without advancing SQLite cursor; recovery succeeds cleanly.
17. **Agent Process Restart**: Fresh runtime instance reloads committed cursors from SQLite without re-syncing existing records.
18. **Log Privacy Scan**: Automated scan of backend process logs confirms zero leaked API keys, tokens, or plaintext passwords.

---

## Canonical Runner

To execute the test suite:
```bash
./scripts/run_pre_one_e2e.sh
```

Prerequisites:
- PostgreSQL 16 running on port 5432 (canonical db: `cashback_e2e_local` locally, `cashback_e2e_ci` in CI; strict `cashback_e2e_` prefix required, no query overrides, `SELECT current_database()` verified before migrations)
- Redis 7 running on port 6379 (dedicated non-zero db: 14 via single `REDIS_URL`; DB must be empty, DB0 rejected, no arbitrary FLUSHDB)
- Python environment with requirements installed
- Backend runs in `development` mode with ephemeral secrets so real RedisRateLimiter is exercised
