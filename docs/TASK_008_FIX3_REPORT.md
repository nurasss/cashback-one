# TASK-008-FIX3 Report

## Root Cause
- In `StateStore._get_connection()`, `PRAGMA journal_mode=WAL;` was executed on initial connection before schema validation or version checks were performed.
- Because `journal_mode=WAL` is a persistent modification to the SQLite file header, even when an unrelated foreign database was subsequently rejected with `StateSchemaUnsupportedError`, its journal mode had already been mutated from `delete` to `wal`.

## Read-Only Validation Phase
- Separated database connection semantics into:
  - `_open_readonly_connection()`: Opens existing non-empty files strictly in read-only mode via SQLite URI (`file:<path>?mode=ro`, `uri=True`). At this stage, SQLite physically rejects any write operations or mutating PRAGMAs.
  - `_open_agent_writable_connection()`: Opens the database in read-write mode and applies `PRAGMA journal_mode=WAL;` and `PRAGMA synchronous=NORMAL;`.
- Before executing any writable operations on an existing non-empty file, `StateStore._init_db()` performs a strict read-only inspection:
  1. `PRAGMA quick_check;`
  2. `PRAGMA user_version;`
  3. `sqlite_master` table inspection
  4. `PRAGMA table_info(agent_checkpoint);` column validation

## Foreign SQLite Protection
- An existing SQLite database containing foreign tables (e.g. `unrelated`) and lacking `agent_checkpoint` is rejected during the read-only phase with `StateDbNotAgentDatabaseError` (`STATE_SCHEMA_UNSUPPORTED`).
- Verified via strengthened `test_foreign_sqlite_no_silent_mutation`:
  - `journal_mode` remains strictly `delete` (unmodified).
  - `user_version` remains `0`.
  - Foreign tables remain intact with zero mutations.

## Future Version Protection
- An existing database with `user_version > STATE_SCHEMA_VERSION` (e.g. `99`) is rejected during the read-only phase with `StateSchemaUnsupportedError`.
- Verified via `test_unsupported_future_schema_version`:
  - `journal_mode` remains `delete`.
  - `user_version` remains `99`.
  - No writes or header changes occur.

## Incompatible Legacy Protection
- An existing database with `user_version = 0` and an `agent_checkpoint` table missing required columns is rejected during the read-only phase.
- Verified via `test_incompatible_checkpoint_structure_rejected`:
  - `journal_mode` remains `delete`.
  - `user_version` remains `0`.
  - Schema remains untouched.

## Valid Legacy v0 Migration
- Legitimate legacy TASK-008 databases with `user_version = 0` and complete `agent_checkpoint` structure pass read-only validation.
- Only after successful validation does `StateStore` open the writable connection, enable WAL mode, and stamp `PRAGMA user_version = 1`.
- Existing committed cursors (e.g. `'C123'`) are preserved intact.

## Agent Tests
- **Pytest:** 56 passed in 2.50s (`pytest agent/tests -v`)
- All 56 tests passing across contracts, retry bounds, schema migrations, and SQLite protections.

## Backend Regression
- **Pytest (Unit & Integration):** 176 passed, 29 skipped in 13.44s (`pytest -v -m "not slow"`)
- Zero regressions across customer auth, customer wallet, agent sync, Wappi webhooks, and rate limiters.

## PostgreSQL Regression
- **Pytest (PostgreSQL Concurrency):** 29 passed in 7.85s (`POSTGRES_TEST_URL=... pytest -v tests/test_postgres_*.py`)
- All 29 PostgreSQL concurrency tests passed.

## Ruff
- `ruff check agent/src agent/tests` -> All checks passed!
- `ruff check app tests migrations` -> All checks passed!

## Mypy
- `mypy agent/src agent/tests` -> Success: no issues found in 25 source files
- `mypy app migrations` -> Success: no issues found in 41 source files

## Compileall
- `python3 -m compileall agent/src agent/tests` -> Passed with 0 errors
- `python3 -m compileall app tests migrations` -> Passed with 0 errors

## Windows Verification Status
- `REAL_WINDOWS_SERVICE = NOT VERIFIED`

## COM Verification Status
- `REAL_V83_COMCONNECTOR = NOT VERIFIED`

## ONE Mapping Status
- `REAL_ONE_MAPPING = NOT IMPLEMENTED`

## Git Status
- Clean working directory following forward commit.

## Branch
- `main`

## HEAD
- `5a9e3bc82eb0ecb6f72dc6c185ca82b1399f6aa6` (forward commit on main)
