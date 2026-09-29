# TASK-008-FIX2 Report

## Heartbeat Contract Fix
- The Cloud Agent's heartbeat URL was corrected from `/agent/sync/heartbeat` to `/agent/heartbeat` matching the accepted TASK-002 backend endpoint (`POST /agent/heartbeat`).
- No backend routes were altered; the Cloud backend contract remains canonical and intact.

## Cloud Endpoint Contract
- Defined explicit route constants in `agent/src/poscenter_loyalty_agent/cloud_client.py`:
  - `CARDS_SYNC_PATH = "/agent/sync/cards"`
  - `TRANSACTIONS_SYNC_PATH = "/agent/sync/transactions"`
  - `HEARTBEAT_PATH = "/agent/heartbeat"`
- `HttpCloudClient.sync_cards`, `sync_transactions`, and `send_heartbeat` use these constants directly.
- Added contract regression tests in `agent/tests/test_cloud_client.py` and `agent/tests/test_backend_contract.py` asserting that `/agent/heartbeat` returns 200 `HeartbeatResult(status="ok")`, while legacy `/agent/sync/heartbeat` returns 404.

## Backoff Maximum Cap
- In `agent/src/poscenter_loyalty_agent/retry.py`, `calculate_backoff` previously added jitter to a capped value, which could exceed `max_seconds` (e.g. `300 * 1.2 = 360`).
- The formula now guarantees `0 < delay <= max_seconds` by applying `min(max_seconds, max(0.01, capped))` after jitter is applied.
- `Retry-After` headers continue to be strictly capped at `max_seconds`.
- Added deterministic tests in `agent/tests/test_retry.py` verifying that delay never exceeds `max_seconds` across attempts, and `Retry-After=1000` with `max=300` returns exactly `300.0`.

## Legacy State DB Validation
- In `agent/src/poscenter_loyalty_agent/state_store.py`, legacy databases created prior to schema versioning (`PRAGMA user_version = 0`) containing an existing `agent_checkpoint` table are verified against all required columns:
  - `id`, `cards_committed_cursor`, `transactions_committed_cursor`, `last_successful_sync_at`, `last_error`, `last_error_at`, `last_heartbeat_at`, `updated_at`.
- Upon successful structural validation, legacy v0 databases are safely stamped to `user_version = 1` while preserving existing cursor positions and checkpoint state.

## Foreign SQLite Protection
- If an existing SQLite database with `user_version = 0` contains unrelated user tables (or an incompatible `agent_checkpoint` table), `StateStore` refuses to mutate the database.
- It raises `StateDbNotAgentDatabaseError` (subclass of `StateSchemaUnsupportedError`) without executing `CREATE TABLE` and without stamping `PRAGMA user_version`.
- Verified via `test_foreign_sqlite_no_silent_mutation` confirming that `agent_checkpoint` is not created, `user_version` remains 0, and foreign tables remain completely untouched.

## Log Rotation Configuration
- In `agent/src/poscenter_loyalty_agent/main.py` (`cmd_run`) and `agent/src/poscenter_loyalty_agent/windows_service.py` (`SvcDoRun`), `settings.log_max_bytes` and `settings.log_backup_count` are now passed to `configure_logging(..., max_bytes=settings.log_max_bytes, backup_count=settings.log_backup_count)`.
- `AgentSettings` in `config.py` supports both `log_max_bytes` / `agent_log_max_bytes` and `log_backup_count` / `agent_log_backup_count` via `AliasChoices`.
- `cmd_check_config` prints `Log Rotation Max Bytes` and `Log Backup Count`.
- Unit tests added in `agent/tests/test_cli.py` and `agent/tests/test_windows_service.py`.

## Agent Tests
- **Pytest:** 55 passed in 2.42s (`pytest agent/tests -v`)
- Covers all 47 previous tests plus 8 new contract, jitter capping, legacy v0, foreign SQLite, and log rotation tests.

## Backend Regression
- **Pytest (Unit & Integration):** 176 passed, 29 skipped in 15.89s (`pytest -v -m "not slow"`)
- Zero regressions across customer auth, customer wallet, agent sync, Wappi webhooks, SMS fallback, and rate limiters.

## PostgreSQL Regression
- **Pytest (PostgreSQL Concurrency):** 29 passed in 8.22s (`POSTGRES_TEST_URL=... pytest -v tests/test_postgres_*.py`)
- All concurrency and row-level locking tests pass without error.

## Windows Verification Status
- `REAL_WINDOWS_SERVICE = NOT VERIFIED`

## COM Verification Status
- `REAL_V83_COMCONNECTOR = NOT VERIFIED`

## ONE Mapping Status
- `REAL_ONE_MAPPING = NOT IMPLEMENTED`

## Ruff
- `ruff check agent/src agent/tests` -> All checks passed (0 errors)
- `ruff check app tests migrations` -> All checks passed (0 errors)

## Mypy
- `mypy agent/src agent/tests` -> Success: no issues found in 25 source files
- `mypy app migrations` -> Success: no issues found in 41 source files

## Compileall
- `python3 -m compileall agent/src agent/tests` -> Passed with 0 errors
- `python3 -m compileall app tests migrations` -> Passed with 0 errors

## Git Status
- Clean working directory following forward commit.

## Branch
- `main`

## HEAD
- `10cead8` (forward commit on main)
