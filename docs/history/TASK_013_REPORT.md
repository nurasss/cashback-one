# TASK-013 Delivery Report: Pre-ONE End-to-End Integration Harness

**Date**: 2026-10-03  
**Role**: Senior Integration / Backend / QA Engineer  
**Branch**: `task-013-pre-one-e2e`  
**Accepted Baseline**: `314b789c177014b912cd84eba9c597e33d8d683c` (`task-012-fix-c`)  

---

## 1. Executive Summary

TASK-013 establishes a comprehensive, reproducible end-to-end integration test harness that exercises the complete operational chain of POSCENTER Loyalty before connecting to real POSCENTER ONE.

The harness runs against real services:
- **Real PostgreSQL 16**: Test database `poscenter_loyalty_e2e_test` with all 9 Alembic migrations applied to head.
- **Real Redis 7**: Native Redis daemon on port 6379 for rate limits and auth state.
- **Real Backend Process**: Independent Uvicorn ASGI HTTP server process listening on loopback.
- **Real Agent Synchronization Client**: `HttpCloudClient` interacting with `AgentRuntime`, `StateStore` (SQLite), and `ProcessLock`.

---

## 2. Test-Double Boundary & Preservation of Invariants

- **`TestLoyaltySource`**: Located exclusively in `e2e/source.py`. Provides in-memory typed DTOs conforming to the `LoyaltySource` protocol without speculative assumptions about 1C metadata or COM structures.
- **Production Code Isolation**: No fake ONE connector, no bypass authentication headers, and no test endpoints exist in the production application codebase.
- **Explicit ONE Deferred Statuses Maintained**:
  ```ini
  REAL_WINDOWS_SERVICE = NOT VERIFIED
  REAL_V83_COMCONNECTOR = NOT VERIFIED
  REAL_ONE_CONNECTION = NOT VERIFIED
  REAL_ONE_METADATA_DISCOVERY = NOT VERIFIED
  REAL_ONE_MAPPING = NOT VERIFIED
  ```

---

## 3. Scope of Scenarios Verified

The test suite in `e2e/test_pre_one_flow.py` verifies all required integration checkpoints:

1. **Admin HTTP Authentication**: Superadmin logs in via real HTTP `POST /admin/auth/login`, receives JWT access token and `admin_refresh` cookie.
2. **Business A Provisioning**: Superadmin creates Business A via `POST /admin/businesses`.
3. **Agent A Provisioning & Key Disclosure**: Agent A is provisioned via `POST /admin/agents` with one-time API key disclosure (`key_hash` remains strictly internal).
4. **Heartbeat Lifecycle**: `HttpCloudClient` sends heartbeat to `/agent/heartbeat`, verified by `last_seen_at` updating on `/admin/agents/{id}`.
5. **Card & Transaction Ingestion**: Card A with 13-digit barcode `0123456789012` (preserving leading zero) and Transaction T1 synchronized via real HTTP `/agent/sync/*`.
6. **Customer WhatsApp Reverse Login**: Challenge generated via `POST /auth/challenge`, confirmed via simulated authenticated Wappi webhook message to `POST /webhooks/wappi`, and exchanged for customer JWT token via `GET /auth/challenge/{id}`.
7. **Customer Wallet Auto-Binding**: Customer `GET /me/cards` auto-binds Card A by phone match; verifies 13-digit barcode integrity, balance (`1000.0000`), and transaction history (`GET /me/cards/{id}/transactions`).
8. **Second Sync Propagation**: Card balance updated to `1350.0000` and Transaction T2 appended; customer wallet immediately reflects new balance and 2 transactions without server restart.
9. **Idempotency**: Duplicate synchronization pass leaves card count and transaction count unaltered.
10. **Multi-Tenant Partitioning**: Business B and Agent B created; Agent B syncs are strictly isolated, and Customer A cannot view Card B.
11. **Manager Tenant Isolation**: Business Manager A authenticated via HTTP only sees Business A agents and cards, cannot see Business B, and receives 403 on `/admin/businesses`.
12. **Superadmin Cross-Tenant Oversight**: Superadmin dashboard and listings view aggregate metrics across all businesses and agents.
13. **Full-Resync Command Persistence**: `POST /admin/agents/{id}/full-resync` registers a durable resync command with status `pending` (execution deferred).
14. **Agent Revocation**: `POST /admin/agents/{id}/revoke` disables Agent B; subsequent agent requests receive `401 Unauthorized`.
15. **Agent Key Rotation**: `POST /admin/agents/{id}/rotate-key` issues new key; old key rejected, new key accepted.
16. **Fault & Retry Safety**: Network transport failure stops sync cycle without advancing SQLite cursor; subsequent retry succeeds cleanly.
17. **Agent Process Restart**: Fresh runtime instance reloads committed cursors from SQLite without re-syncing existing records.
18. **Log Privacy Scan**: Automated scan of backend process log confirms zero API keys, tokens, or plaintext passwords logged.

---

## 4. Execution Evidence

### Canonical E2E Command
```bash
./scripts/run_pre_one_e2e.sh
```

### E2E Run #1
```
============================= test session starts ==============================
collected 4 items

e2e/test_pre_one_flow.py::test_pre_one_e2e_full_chain PASSED
e2e/test_pre_one_flow.py::test_pre_one_e2e_retry_and_cursor_safety PASSED
e2e/test_pre_one_flow.py::test_pre_one_e2e_agent_restart PASSED
e2e/test_pre_one_flow.py::test_pre_one_e2e_log_privacy PASSED

============================== 4 passed in 20.14s ==============================
SUCCESS: All Pre-ONE End-to-End integration scenarios passed.
```

### E2E Run #2 (Consecutive Determinism Verification)
```
============================= test session starts ==============================
collected 4 items

e2e/test_pre_one_flow.py::test_pre_one_e2e_full_chain PASSED
e2e/test_pre_one_flow.py::test_pre_one_e2e_retry_and_cursor_safety PASSED
e2e/test_pre_one_flow.py::test_pre_one_e2e_agent_restart PASSED
e2e/test_pre_one_flow.py::test_pre_one_e2e_log_privacy PASSED

============================== 4 passed in 20.54s ==============================
SUCCESS: All Pre-ONE End-to-End integration scenarios passed.
```

---

## 5. Full Regression Verification Summary

| Test Suite | Scope | Result | Time |
| :--- | :--- | :--- | :--- |
| **Pre-ONE E2E Suite** | Full chain, Retry, Restart, Log Privacy | **4 / 4 PASSED** | 20.5s |
| **Backend Suite** | Unit, API, Auth, Security, Runtime | **265 PASSED, 36 SKIPPED** | 33.3s |
| **PostgreSQL Concurrency** | Concurrency, Locks, Isolation | **36 / 36 PASSED** | 15.4s |
| **Agent Suite** | Runtime, State Store, Retries, Protocol | **76 / 76 PASSED** | 2.9s |
| **Admin SPA Suite** | Typecheck, Lint, Vitest, Vite Build | **44 / 44 PASSED** | 10.2s |
| **Mobile Suite** | Typecheck, Lint, Jest Flow/Component | **81 / 81 PASSED** | 4.1s |
| **Backend Lint/Types** | Ruff + Mypy + Compileall | **0 ERRORS** | - |
| **Agent Lint/Types** | Ruff + Mypy + Compileall | **0 ERRORS** | - |

---

## 6. Changed & Created Files

### Created:
- `e2e/__init__.py`
- `e2e/conftest.py`: Fixtures and path resolution for E2E harness.
- `e2e/source.py`: `TestLoyaltySource` implementation of `LoyaltySource` protocol.
- `e2e/harness.py`: Real Uvicorn, DB migrations, Redis flush, and admin bootstrap harness.
- `e2e/test_pre_one_flow.py`: Comprehensive 18-step integration test flow.
- `e2e/README.md`: Harness documentation and architecture reference.
- `scripts/run_pre_one_e2e.sh`: Canonical one-command executable runner.
- `docs/PRE_ONE_E2E.md`: Detailed harness architecture and boundaries.
- `docs/TASK_013_REPORT.md`: This delivery report.

### Modified:
- `backend/app/services/admin_security.py`: Allowed explicit insecure HTTP in `test` environment when `admin_allow_insecure_http` is explicitly enabled (matching development semantics while remaining strictly forbidden in `production`).
- `.github/workflows/ci.yml`: Added `pre-one-e2e` job with PostgreSQL 16 and Redis 7 services running `./scripts/run_pre_one_e2e.sh`.

---

## 7. Next Milestone Gate

TASK-013 is complete. Per project constraints, the implementation stops here.
The next step is **TASK-009B Real ONE Discovery** on the physical Windows / 1C target host.
