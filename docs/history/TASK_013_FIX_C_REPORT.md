# TASK-013 FIX-C Report: Preserve PostgreSQL Credentials Without Leaking Them

Date: 2026-10-03
Branch: `task-013-fix-c`
Baseline branch: `task-013-fix-b`
Baseline HEAD: `f522d714e2094a968b47c669cc67fbfb59f4e3d6`
New HEAD: pending commit on `task-013-fix-c`
Git Status: clean (after commit)

## Summary

Narrow FIX-C over FIX-B. Fixed only PostgreSQL derived-URL handling in
`e2e/test_resource_safety.py` (+ minimal validator acceptance for URL objects,
runner fallback without hardcoded username). All FIX-B safety/privacy guarantees
preserved. No loyalty flow, Redis, ONE/COM/Stage0 changes.

- `str(SQLAlchemy URL)` masks password to `***`; using it as connection DSN breaks
  SCRAM/password auth (`InvalidPasswordError`). Fixed to URL objects end-to-end,
  `render_as_string(hide_password=False)` only at single env-subprocess boundary.
- Connection vs display strictly separated (safe host/port/database only).
- Preservation + privacy unit tests added.
- Real password-auth PG (`review_ci`/`cashback_e2e_ci`, SCRAM enforced) fully passes.
- Two canonical password-auth runs PASS, ownership/sentinel/Redis/idempotency/T3 kept.
- Full regressions PASS. CI remains password-auth (no weakening).

## Baseline

- `git status`: clean on `task-013-fix-b`
- `git branch --show-current`: `task-013-fix-b`
- `git rev-parse HEAD`: `f522d714e2094a968b47c669cc67fbfb59f4e3d6`
- Created `git switch -c task-013-fix-c`, no amend.
- Reviewer-confirmed FIX-B functionality preserved (preflight, refusal, ownership,
  Redis safety, privacy, cleanup, no PAUSE, isolated outage, limiter, redelivery,
  idempotency, T3, runs, regressions).

## Root Cause

`e2e/test_resource_safety.py`:

```python
u = make_url(base)
new_u = u.set(database=dbname)
return str(new_u)   # BUG: masks password to ***
```

`URL.__str__()` renders `postgresql+asyncpg://review_ci:***@...`, then used as
connection URL for maintenance/safety DBs. On SCRAM/password PG → `InvalidPasswordError`,
breaking ownership/sentinel/CI password-auth runs. Trust-auth locally masked the bug.

## SQLAlchemy URL Masking

Verified:

- `str(url)` → `...://review_ci:***@127.0.0.1:5432/postgres` (masked, unusable for auth)
- `url.render_as_string(hide_password=False)` → `...://review_ci:fixture-db-password@...` (real)
- `url.password` attr → real password preserved on object
- `make_url(url_object)` preserves password
- `create_async_engine(url_object)` preferred (no string round-trip)

## Connection URL Handling

- Found all E2E `str(url)`/`f"{url}"` DSN uses: single site `_pg_url_for_db` (fixed).
  Harness log lines only use `base_url` (no DB URL). No `"%s" % url` DSN.
- Rule now: prefer URL objects everywhere; string only via
  `render_as_string(hide_password=False)` immediately at env/subprocess need,
  never stored/logged/displayed/test-ID.
- `_pg_exec`/`_pg_scalar` accept `str | URL`, pass object directly to
  `create_async_engine` (preferred). Errors remapped via `_safe_pg_error`
  preserving safe keywords (`already exists`, `permission denied`) without raw URL.
- Assertions never interpolate URL objects (`assert ..., "safe message"` only).

## Maintenance URL

`_pg_maintenance_url()` → `_pg_url_for_db("postgres")` now returns URL object:

- driver/username/REAL password/host/port preserved, only `database=postgres` changed,
  no query overrides. Verified `username==review_ci`, `password==fixture-db-password`,
  host/port unchanged. Never `str()` for connect.

## Safety Database URL

`_pg_url_for_db("cashback_e2e_safety_<uuid>")` same: only database changed, real password
preserved, URL object returned. `***` never used as password (asserted in test).

## Credential Preservation Tests

New `test_derived_urls_preserve_real_password`:

- base `review_ci:fixture-db-password@127.0.0.1:5432/cashback_e2e_ci`
- maint: user/host/port preserved, `database==postgres`, no `***` in
  `render_as_string(hide_password=False)`
- safety: password preserved, db == generated, `str()` masking demonstrated to prove
  why `str()` must not be used, real string contains password exactly once.

New `test_derived_url_failure_hides_marker_password`: derived URL with marker,
validation + unreachable-port connect failures hide marker.

## Credential Privacy Tests

- Existing marker tests retained + new derived failure test.
- All failure messages via `E2ESafetyError` (no URL/password/query/username).
- `assert marker not in combined, "safe message"` (no value interpolation).
- Verified: DB marker `marker-db-*`, Redis `?password=marker-redis-*` → preflight/runner
  exit≠0, marker 0 times, no raw URL, pytest not started.

## Password Authenticated PostgreSQL

Reviewer-style local PG:

- `CREATE USER review_ci WITH PASSWORD 'fixture-review-ci-pw-9f8e7d' CREATEDB`
- `CREATE DATABASE cashback_e2e_ci OWNER review_ci`
- `pg_hba.conf`: `host all review_ci 127.0.0.1/32 scram-sha-256` (all DBs), reload.
- Wrong/`***` password → `FATAL: password authentication failed`; correct → ok.
- No production credentials used. `dump.rdb` untouched, pg_hba change is local env only
  (not committed).

## Canonical E2E Password-Auth Run #1

```
POSTGRES_E2E_URL='postgresql+asyncpg://review_ci:fixture-review-ci-pw-9f8e7d@127.0.0.1:5432/cashback_e2e_ci'
REDIS_URL='redis://127.0.0.1:6379/14' ./scripts/run_pre_one_e2e.sh
32 passed in 51.25s (5 flow + 27 safety)
SUCCESS, no InvalidPasswordError, ownership tests executed (not skipped)
```

## Canonical E2E Password-Auth Run #2

```
32 passed in 32.35s
SUCCESS, no manual cleanup between
```

Both password-auth (preferred per §19). Safety count 27 (was 25: + preservation + derived-failure).

## Postgres Ownership Tests

On password-auth PG, all executed (no skip):

- owned lifecycle create/drop PASS
- existing never adopted PASS (safe `already exists` preserved via `_safe_pg_error`)
- non-E2E sentinel preserved PASS
- runner refuses unsafe DB before pytest PASS (preflight + full runner, sentinel/DB survive)

## Unsafe DB Sentinel Regression

Targeted: unique `review_safety_<hex>` + sentinel → preflight + full runner refuse,
pytest 0, sentinel/DB survive, owned DROP. Also manual `reviewer_guard_db` probe from
FIX-B still valid (code path unchanged except password preservation).

## Redis Safety Regression

- Busy canonical DB (owned UUID key) → preflight + runner refuse `not empty`, key survives.
- DB15 `dbsize 0`, untouched after password-auth runs.
- DB0/query pure validation, no connect. Redis privacy markers 0.

## Idempotency/T3 Regression

Unchanged scenarios, password-auth runs confirm:

- Card A 1, Card B 1, tx-001 1, tx-002 1, tx-003 1, tx-b-001 1
- T3 failure → absent/cursor unchanged (dead `127.0.0.1:18999` real HTTP)
- Retry → exactly 1, replay → still 1, non-empty replay >0

## Backend Regression

```
pytest -v -m "not slow" → 265 passed, 36 skipped
ruff check app tests migrations → All checks passed
mypy app migrations → Success 57 files
compileall → ok
```

## PostgreSQL Regression

```
POSTGRES_TEST_URL=... pytest tests/test_postgres_*.py → 36 passed
```

## Admin Regression

```
npm test 44 passed, typecheck/lint/build ok, audit 0 high
```

## Mobile Regression

```
npm test 81 passed, typecheck/lint ok, export dist ok
```

## Agent Regression

```
PYTHONPATH=src pytest 76 passed, ruff/mypy/compileall ok
```

## CI Compatibility

`.github/workflows/ci.yml` unchanged (still `loyalty:fixture-ci-.../cashback_e2e_ci` password-auth).
Suite now works with it because derived URLs preserve password via objects.
No change to trust/no-password (no weakening). Safety tests derive from env
(no `nuras`, no `cashback_e2e_local`, no DB15), `loyalty` superuser can CREATEDB.

Runner fallback fixed without hardcoded username: `REPO_ROOT/.venv` → `$HOME/Desktop/...`
(no `nuras` string) → `python3`. Default DSN `postgresql+asyncpg://localhost/...`
(no user). Verified `grep -rn nuras e2e/*.py` clean (except `$HOME` path).

## Files Changed

- `e2e/test_resource_safety.py` (URL objects, safe errors, preservation/privacy tests)
- `e2e/harness.py` (validators accept URL objects, minimal, no behavior change)
- `scripts/run_pre_one_e2e.sh` (`$HOME` fallback, no-user default DSN)
- `docs/TASK_013_FIX_C_REPORT.md` (this report)

Small diff as required (3 code files + report). No backend/Agent/Redis/Admin/Mobile/migrations/ONE.

## Branch

`task-013-fix-c` (from `task-013-fix-b`)

## HEAD

Baseline `f522d714e2094a968b47c669cc67fbfb59f4e3d6`, new pending
`fix(e2e): preserve postgres credentials in derived urls`

## Git Status

Clean on `task-013-fix-c` after commit.
