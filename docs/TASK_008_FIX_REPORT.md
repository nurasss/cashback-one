# TASK-008 PATCH REPORT: Windows Agent Audit Remediation

## 1. Overview & Objective
This patch resolves all 12 defects identified during the independent audit of the Windows Agent runtime foundation (TASK-008) without adding new product business logic. All quality gates across both the Windows Agent and the Cloud Backend pass without regression.

Initial HEAD: `90c13c55a2acbc86047eb67e26752d0d757e7a6b`
Branch: `main`

---

## 2. Audit Findings & Remediations

### 1. TLS Verification — P1
- **Defect:** `cloud_api_verify_ssl` allowed disabling TLS verification in test/dev environments, introducing security risks.
- **Fix:** Removed environment checks. `cloud_api_verify_ssl` evaluates strictly to `True` by default across all environments. There is zero `verify=False` in `agent/src/`. Verified via dedicated test asserting `cloud_api_verify_ssl is True` in test, development, and production environments, and a regression test scanning agent source files.

### 2. Max Pages Per Cycle Separate Accounting — P1
- **Defect:** Card and transaction streams shared a single cycle counter or could cause stream starvation if cards dominated.
- **Fix:** Each stream (`cards` and `transactions`) maintains its own independent page budget (`max_pages_per_cycle`). Even when the card stream reaches its page limit in a cycle, the transaction stream processes up to its full page limit.

### 3. Empty Page with `has_more=True` Source Protocol Error — P1
- **Defect:** An adapter returning `items=[]` with `has_more=True` could cause an infinite busy-loop.
- **Fix:** Added `SourceProtocolError` (`SOURCE_PROTOCOL_ERROR`). If `items` is empty while `has_more=True`, runtime raises `SourceProtocolError`, skips advancing the cursor, sends zero requests to Cloud API, and triggers exponential backoff.

### 4. Real Crash-After-ACK Fault Injection Test — P1
- **Defect:** Previous test only verified happy-path cursor commit.
- **Fix:** Added `test_real_crash_after_ack_fault_injection` simulating a crash/exception inside `StateStore.commit_cursor` immediately after the Cloud API returns a 200 ACK. On restart, the agent re-reads the unadvanced cursor from durable storage and safely re-submits the batch (at-least-once delivery contract).

### 5. Durable State Store Schema Versioning & Corruption Rejection — P1
- **Defect:** Schema lacked explicit versioning (`PRAGMA user_version`) and corrupted non-SQLite files were not safely handled.
- **Fix:**
  - Added `STATE_SCHEMA_VERSION = 1` managed via SQLite `PRAGMA user_version`.
  - Upgrades legacy v0 schemas by creating tables and stamping `PRAGMA user_version = 1`.
  - Future/unsupported schema versions raise `StateSchemaUnsupportedError` (`STATE_SCHEMA_UNSUPPORTED`).
  - Corrupted files detected via `PRAGMA quick_check;` raise `StateDbCorruptedError` (`STATE_DB_CORRUPTED`) without deleting the file.
  - Stream arguments validated against `VALID_STREAMS = {"cards", "transactions"}`.

### 6. Strict Secrecy of `ONE_CONNECTION_STRING` — P1
- **Defect:** Connection string could theoretically be logged or leaked through COM error details.
- **Fix:** Sanitized all log messages to generic `"Connecting to POSCENTER ONE via COM"`. Replaced low-level COM exception details with `OneComConnectionError("ONE_CONNECTION_FAILED: Unable to establish COM connection.") from None`. Verified via regex and keyword assertions across captured logs and exception strings.

### 7. Cloud Malformed 2xx Response Protocol Handling — P1
- **Defect:** Invalid JSON or missing required fields in 200 OK responses from Cloud API raised unclassified `ValidationError` or `json.JSONDecodeError`.
- **Fix:** Introduced `CloudProtocolError` (`CLOUD_PROTOCOL_ERROR`), inheriting from `CloudRetryableError`. Response bodies are validated with Pydantic (`HeartbeatResult`, `CardsSyncResult`, `TransactionsSyncResult`). Malformed responses trigger retry backoff, and raw payloads are never dumped to production logs.

### 8. Configurable Retry & Backoff Bounds — P2
- **Defect:** Backoff bounds were partially hardcoded.
- **Fix:** Added `agent_sync_backoff_initial_seconds` (default 2.0s, > 0), `agent_sync_backoff_max_seconds` (default 300.0s, >= 1.0s), and `agent_sync_backoff_jitter_ratio` (default 0.2, [0.0, 1.0]). Pydantic model validator enforces `max_seconds >= initial_seconds`. `Retry-After` headers are capped at `max_seconds`.

### 9. Timezone-Aware Datetimes Contract — P2
- **Defect:** Naive datetimes could bypass validation and corrupt UTC timestamps.
- **Fix:** Added `ensure_timezone_aware` validators rejecting naive datetimes on `CardSyncItem.updated_at`, `TransactionSyncItem.occurred_at`, and `HeartbeatPayload.last_successful_sync_at`. `AgentStatus.started_at` defaults to `datetime.now(UTC)`.

### 10. De-speculation of Stage 0 Documentation — P2
- **Defect:** `docs/ONE_STAGE0_REQUIRED.md` and `docs/AGENT_ARCHITECTURE.md` contained hypothetical 1C table/column names.
- **Fix:** Rewrote documentation using neutral terminology ("Cards Source", "Ledger/Transactions Source", "Modification Timestamp", "Monotonic Sequence ID"). Explicitly documented the Opaque String Cursor Contract.

### 11. Bounded Graceful Shutdown — P2
- **Defect:** Shutdown wait could theoretically hang if an in-flight HTTP request hung.
- **Fix:** Added `agent_shutdown_grace_seconds` (default 30.0s). Shutdown allows in-flight sync passes to finish committing within the grace period; remaining tasks are forcibly cancelled after grace expires.

### 12. Opaque Cursor Privacy in Logs & CLI — P2
- **Defect:** Cursor values were displayed in CLI status and debug logs.
- **Fix:** Raw cursor values are never logged or exposed. Logs record stream name and record count. CLI `cmd_status` reports cursor presence as `set` or `(none)`.

---

## 3. Explicit Verification Declarations

As required by the POSCENTER ONE Stage 0 integration boundaries:

- `REAL_WINDOWS_SERVICE = NOT VERIFIED` (Tested via mock/platform guards on non-Windows host)
- `REAL_V83_COMCONNECTOR = NOT VERIFIED` (Tested via mock COM dispatcher and platform guards)
- `REAL_ONE_MAPPING = NOT IMPLEMENTED` (Awaiting physical POSCENTER ONE 1C schema discovery)

---

## 4. Quality Gate Verification Results

### Windows Agent (`agent/`)
- **Unit & Integration Tests:** 47 passed in 2.60s (`pytest agent/tests -v`)
- **Linter:** Passed with 0 errors (`ruff check agent/src agent/tests`)
- **Type Checker:** Passed with 0 issues in 25 source files (`mypy agent/src agent/tests`)
- **Bytecode Compilation:** Passed with 0 errors (`python3 -m compileall agent/src agent/tests`)

### Cloud Backend (`backend/`)
- **Unit & Fast Integration Tests:** 176 passed, 29 skipped in 23.81s (`pytest -v -m "not slow"`)
- **PostgreSQL Concurrency Tests:** 29 passed in 25.80s (`POSTGRES_TEST_URL=... pytest -v tests/test_postgres_*.py`)
- **Linter:** Passed with 0 errors (`ruff check app tests migrations`)
- **Type Checker:** Passed with 0 issues in 41 source files (`mypy app migrations`)
