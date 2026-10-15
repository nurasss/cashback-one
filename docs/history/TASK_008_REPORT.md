# TASK-008 Implementation Report

## Windows Agent Runtime + Reliable Cloud Sync Foundation

- **Status**: READY FOR ACCEPTANCE
- **Initial HEAD**: `796ff7d134182fd253ccfce0d0913976fb0d3bb1`
- **Branch**: `main`
- **Governing Specification**: `TZ_loyalty_app_v1.1` & Task 008 Requirements

---

## 1. Executive Summary

TASK-008 establishes the full production runtime framework for the on-premises **POSCENTER Loyalty Windows Agent** (`poscenter-loyalty-agent`).

The agent is engineered to run as an autonomous Windows background service (or interactive CLI tool), ensuring reliable, at-least-once synchronization of loyalty cards and bonus transactions from local POSCENTER ONE data stores to the central Cloud API, accompanied by independent health reporting.

---

## 2. Explicit Verification Declarations

In strict adherence to Stage 0 constraints and development host limitations:

```text
REAL_WINDOWS_SERVICE   = NOT VERIFIED (Mac OS environment; guarded against ModuleNotFoundError)
REAL_V83_COMCONNECTOR  = NOT VERIFIED (Mac OS environment; guarded against ModuleNotFoundError)
REAL_ONE_MAPPING       = NOT IMPLEMENTED (Stage 0 discovery required on pilot 1C database)
```

- Real POSCENTER ONE 1C metadata object names (e.g. `Справочники.ДисконтныеКарты`) are **NOT** guessed or hardcoded.
- The agent defaults to `ONE_ADAPTER_MODE=stub`, which raises `ONE_MAPPING_NOT_CONFIGURED` pointing explicitly to `docs/ONE_STAGE0_REQUIRED.md`.

---

## 3. Implemented Modules & Architecture

### 3.1 Agent Package (`agent/src/poscenter_loyalty_agent/`)

1. **`config.py`**:
   - Pydantic Settings configuration (`AgentSettings`).
   - Production enforcement: HTTPS required, API key minimum 16 characters, `fake` adapter mode strictly forbidden outside `test`.
   - Dynamic path resolution (Windows `ProgramData` vs POSIX `~/.poscenter_loyalty_agent`).

2. **`logging.py`**:
   - Structured logging with `RotatingFileHandler` (10MB, 5 backups).
   - Secret & PII masking filter: scrubs `Pwd=...` passwords, `X-Agent-Key` tokens, phone numbers, and 12-19 digit card barcodes from log streams and exceptions.

3. **`process_lock.py`**:
   - Process singleton lock guaranteeing one active instance per machine/directory.
   - POSIX: `fcntl.flock(LOCK_EX | LOCK_NB)`.
   - Windows: `msvcrt.locking(LK_NBLCK)`.
   - Raises `AGENT_ALREADY_RUNNING` on collision.

4. **`models.py`**:
   - Exact mirror of Backend Cloud Sync contracts (`CardSyncItem`, `CardsSyncPayload`, `TransactionSyncItem`, `TransactionsSyncPayload`, `HeartbeatPayload`).
   - Strict decimal precision (`Numeric(18, 4)` / `Decimal`), barcode regex (`^\d{13}$`), and UTC timestamps.

5. **`state_store.py`**:
   - Durable SQLite repository (`agent_state.db`) using WAL mode.
   - Checkpoint tracking: `cards_committed_cursor`, `transactions_committed_cursor`, `last_successful_sync_at`, `last_heartbeat_at`, `last_error`, `last_error_at`.
   - **Zero PII & Zero Secrets**: Only opaque cursors and sanitized error strings are stored.

6. **`cloud_client.py`**:
   - `CloudClient` Protocol with `HttpCloudClient` and in-memory `FakeCloudClient`.
   - HTTP transport via `httpx.AsyncClient` with reusable connection pool and timeouts.
   - Error categorization:
     - Retryable: HTTP 5xx, Network timeouts/drops, HTTP 429 (`Retry-After` header honored).
     - Non-retryable: HTTP 401/403 (`CloudAuthError`), HTTP 422 (`CloudNonRetryableError`).

7. **`source.py`**:
   - `LoyaltySource` Protocol.
   - `StubLoyaltySource`: Default production-safe implementation raising `ONE_MAPPING_NOT_CONFIGURED`.
   - `FakeLoyaltySource`: Test fixture for pagination, batch limits, and stalled cursor simulation.

8. **`one_com.py`**:
   - Guarded connection seam for `V83.COMConnector`.
   - Cross-platform safe: dynamic lazy import of `win32com.client` only when `sys.platform == 'win32'`.
   - Connection string password sanitization.

9. **`retry.py`**:
   - Exponential backoff with configurable jitter: $\min(\text{max}, \text{initial} \cdot 2^{\text{attempt}}) \pm \text{jitter}$.
   - Injectable sleeper for deterministic fast testing.

10. **`runtime.py`**:
    - `AgentRuntime` managing the sync cycle, pagination, cursor progression, independent heartbeat loop, and graceful shutdown (`SIGINT`/`SIGTERM`).
    - **At-Least-Once Delivery**: Cursor advances in SQLite **only after** HTTP 2xx ACK from Cloud API. Crash before commit causes safe re-send on next startup.
    - **Stalled Cursor Detection**: Aborts cycle with `SOURCE_CURSOR_STALLED` if `has_more=True` but cursor did not advance.

11. **`windows_service.py`**:
    - Windows Service wrapper (`POSCENTERLoyaltyAgentService`) subclassing `win32serviceutil.ServiceFramework`.
    - Fully guarded against `ModuleNotFoundError` on non-Windows environments (macOS/Linux).

12. **`main.py`**:
    - CLI commands: `run`, `check-config`, `status`, `service`.

---

## 4. Documentation

- **`docs/ONE_STAGE0_REQUIRED.md`**: Complete Stage 0 discovery guide and technical checklist for pilot database analysis.
- **`docs/AGENT_ARCHITECTURE.md`**: Full architectural specification with Mermaid diagram, state machine, and Windows deployment steps.
- **`agent/README.md` & `README.md`**: Updated documentation reflecting TASK-008 additions.

---

## 5. Quality Gate Results

### 5.1 Agent Quality Gates (`agent/`)
- `python3 -m compileall src tests`: **0 errors** (all 25 files compiled successfully)
- `ruff check src tests`: **0 errors** (All checks passed)
- `mypy src tests`: **0 errors** (Success: no issues found in 25 source files, strict mode)
- `pytest tests/ -v`: **32 passed, 0 failed in 0.94s**
  - `test_config.py` (5 tests)
  - `test_state_store.py` (4 tests)
  - `test_cloud_client.py` (2 tests)
  - `test_source.py` (3 tests)
  - `test_retry.py` (2 tests)
  - `test_process_lock.py` (3 tests)
  - `test_one_com.py` (2 tests)
  - `test_windows_service.py` (1 test)
  - `test_heartbeat.py` (1 test)
  - `test_runtime_sync.py` (4 tests)
  - `test_backend_contract.py` (3 tests)
  - `test_cli.py` (2 tests)

### 5.2 Backend Regression Quality Gates (`backend/`)
- `python3 -m compileall app tests`: **0 errors**
- `ruff check app tests`: **0 errors**
- `mypy app`: **0 errors** (Success: no issues found in 33 source files, strict mode)
- `pytest -v -m "not slow"`: **176 passed, 29 skipped in 26.99s** (0 regressions)
- `POSTGRES_TEST_URL="postgresql+asyncpg://nuras@localhost:5432/poscenter_loyalty_test" pytest -v tests/test_postgres_*.py`:
  - **29 passed, 0 failed in 13.43s** (100% passing across all concurrency suites: PG-CONC-01..04, PG-BIND-01..04, PG-AUTH-01..06, PG-SMS-01..04, PG-WALLET-01..05, PG-WAPPI-01..04)

---

## 6. Conclusion

TASK-008 is complete, fully tested, and ready for acceptance.
