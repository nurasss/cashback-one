# TASK-013 FIX-B Report: Make the E2E Safety Suite Itself Safe

Date: 2026-10-03
Branch: `task-013-fix-b`
Baseline branch: `task-013-fix-a`
Baseline HEAD: `625f2ec04a128ca68eac7f968be105f7533660ae`
New HEAD: pending commit on `task-013-fix-b`
Git Status: clean (after commit, `dump.rdb` ignored)

## Summary

Narrow FIX-B over FIX-A. Loyalty functionality untouched (reviewer-confirmed flows
preserved). Blockers were in safety suite itself:

- Canonical preflight `e2e/preflight.py` (same Python code) runs BEFORE pytest;
  unsafe DB/Redis never reaches pytest.
- PG tests use unique owned DBs (`cashback_e2e_safety_<hex>` / `review_safety_<hex>`);
  only test-created DB may be dropped; fixed `reviewer_probe_db` removed.
- Redis tests use canonical `REDIS_URL` only; no DB15/DB13/DB0 connections;
  owned UUID keys only; never FLUSHDB in tests; DB0/query pure validation.
- All safety errors credential-safe (`E2ESafetyError`, no raw URL/password/query).
- Setup-failure test CI-compatible (canonical PG, unreachable localhost port, no `nuras`).
- `CLIENT PAUSE` removed; outage proof via isolated secondary backend with bad Redis.
- `dump.rdb` narrowly ignored (`/dump.rdb`), never committed, never deleted.
- Two canonical runs PASS, idempotency/T3/privacy unchanged, all regressions PASS.

## Baseline

- `git status`: clean except untracked `dump.rdb` (standard Redis artifact, ignored not deleted).
- `git branch --show-current`: `task-013-fix-a`
- `git rev-parse HEAD`: `625f2ec04a128ca68eac7f968be105f7533660ae`
- Created `git switch -c task-013-fix-b`, no amend of `625f2ec`.
- Verified functionality preserved (no rewrite): real PG/Redis/Uvicorn, production
  AgentRuntime/HttpCloudClient, admin/customer auth, RedisRateLimiter, T1/T2,
  redelivery, T3 failure/retry/replay exact counts, isolation, revoke/rotation,
  resync pending, TestLoyaltySource boundary, two runs, regressions.

## Canonical Preflight

New `e2e/preflight.py`:

- Single implementation, no shell/Python duplication. Harness validators reused.
- Reads URLs from environment only (`POSTGRES_E2E_URL`/`POSTGRES_TEST_URL`, `REDIS_URL`/
  `REDIS_E2E_URL` conflict safe). Never CLI args (no `ps`/history leak).
- Steps: structural URL, naming, query reject, `SELECT current_database()` compare,
  Redis URL/DB validation, `PING` + `DBSIZE==0` (non-destructive).
- Success prints only `host/port/database`, `host/port/db`. Failure prints safe reason
  only (e.g. “PostgreSQL database name is not an E2E target”, “Redis DB 0 is not allowed
  for E2E”, “Redis E2E database is not empty”). Never username/password/URL/query.
- `python -m e2e.preflight` exit 0 safe, 1 refuse.
- `scripts/run_pre_one_e2e.sh` now: resolve env → redis ping → `python -m e2e.preflight`
  (fail → “preflight refused … pytest not started”, exit 1) → pytest. Unsafe target never
  reaches pytest or safety tests.

Verified:
- Valid `cashback_e2e_local` + `/14` → exit 0, safe lines.
- Unsafe `reviewer_guard_db` + marker pw → exit 1, `DATABASE SAFETY ABORT…`, marker 0 times.
- Redis `?password=marker` → exit 1, `REDIS SAFETY ABORT…query parameters`, marker 0 times.

## Database Resource Ownership

- Removed fixed `reviewer_probe_db` reuse/drop pattern.
- Helpers derive URLs from canonical env via `make_url(...).set(database=...)`
  (preserves user/host/port/password internally, never logged). No hardcoded `nuras`.
- Unique names: `cashback_e2e_safety_<10hex>` (owned E2E), `review_safety_<10hex>` (owned non-E2E).
- `CREATE DATABASE` must succeed because new; on “already exists” do NOT adopt,
  fail instead of reusing. Track `created_by_this_test`; only if true `DROP`.
- `CREATE/DROP` use `isolation_level="AUTOCOMMIT"` (fixes transaction-block error).
- Tests: `test_pg_owned_lifecycle_create_and_drop` (create→sentinel→verify→drop owned),
  `test_pg_existing_db_never_adopted` (collision → owned=False → no drop → still exists).

## Unsafe Database Runner Refusal

- `test_non_e2e_refusal_preserves_owned_sentinel`: own non-E2E DB + sentinel,
  `validate_e2e_db_url` refuses, sentinel survives, drop owned.
- `test_runner_refuses_unsafe_db_before_pytest`: own unsafe DB + sentinel,
  preflight exit≠0 (no “test session starts”, no raw URL), full
  `./scripts/run_pre_one_e2e.sh` exit≠0 (contains “preflight”, no pytest),
  sentinel + DB survive, then drop owned. Proves runner refuses before pytest.

## PostgreSQL Sentinel Survival

Manual probe: created `reviewer_guard_db` + `sentinel(guard_keepme)`, pointed env there,
harness/preflight refused (`database name is not an E2E target`), `SELECT` still
`guard_keepme`, then dropped owned. Automated tests assert same with unique DBs.

## Redis Resource Ownership

- Harness: single `REDIS_URL`, ownership token `cashback:e2e:owner:<hex>` (no creds/PII)
  created after empty check (`SET nx ex 3600`); cleanup `FLUSHDB` only if same
  host/port/db + token `GET==1`. Otherwise refuse flush. Stronger than boolean.
- Tests: central `owned_keys` pattern (unique `e2e_safety_<uuid>`), `SET` → assert →
  `DELETE` only owned. Never `FLUSHDB` in safety tests.

## Removal of Cross-DB Tests

- Searched `e2e/`: no `/15`, `db=15`, `select(15)`, `sentinel_db15`, `sentinel_fix_a`,
  `busy_key`, `reviewer_probe_db` in source (only old `.pyc` cache, ignored).
- Pure parsing strings like `/0` never connect. All live Redis uses canonical `REDIS_URL`.

## Redis Busy Namespace Refusal

- `test_redis_busy_namespace_refuses_and_preserves_owned_key`: owned key in canonical DB,
  `_live_checks` raises “not empty” (safe, no flush), key survives.
- `test_runner_refuses_busy_redis_before_pytest`: owned `e2e_busy_<uuid>` in canonical DB,
  preflight exit≠0 (“not empty”), full runner exit≠0 (no pytest, contains “preflight”),
  key survives, then delete owned only.

## Redis Sentinel Survival

Same as above: owned sentinel `GET==1` after refusal, then deleted. No other DB touched.
Primary Redis health verified via `PING` in outage test.

## Credential-Safe Failure Output

- Introduced `E2ESafetyError` (subclass `RuntimeError`, same “SAFETY ABORT” match).
- Removed: `f"Unsafe URL: {url}"`, `f"...{sorted(query)}"`, `f"...'{parsed.query}'"`,
  `f"...('{env_redis}' vs ...)"`, `f"...{exc}"` with URL, alembic stdout/stderr propagation.
- New messages generic: “PostgreSQL database name is not an E2E target”,
  “PostgreSQL URL must not contain query parameters”,
  “Redis URL must not contain query parameters”, “Conflicting … Use single REDIS_URL”
  (no URLs), connectivity failures without `exc` message (only type chaining).
- `safe_db_info/safe_redis_info` return host/port/db only; runner prints those only.

## PostgreSQL Failure Privacy

- `test_db_failure_hides_marker_password`: unsafe URL with `marker-db-<hex>` password
  → `E2ESafetyError` without marker.
- `test_preflight_failure_hides_db_marker_password`: preflight subprocess with marker
  password + unsafe DB → exit≠0, combined output marker 0 times, no raw URL, no pytest.
- Full runner probe `fixture-review-db-password-abc123` → exit 1, output safe lines only,
  marker count 0, “test session starts” 0.

## Redis Failure Privacy

- `test_redis_failure_hides_marker_secret`: `?password=marker` → safe error without marker.
- `test_preflight_failure_hides_redis_marker_secret`: preflight with marker query →
  exit≠0, marker 0 times.
- Full runner probe `?password=fixture-review-redis-password-xyz` → exit 1,
  `REDIS SAFETY ABORT: Redis URL must not contain query parameters`, marker 0 times.

## Setup Failure Cleanup

- Fixture already `try: setup/yield/finally: cleanup`. Harness `cleanup()` idempotent,
  partial-init safe (None guards, bounded terminate, engine dispose, token-gated flush,
  tmp removal).
- After failed setup asserts: temp removed, `_engine None`, `_backend_proc None`,
  no orphan (proc terminated), HTTP clients closed (isolated test closes), Agent state
  tmp under harness temp removed with dir.

## CI-Compatible Setup Failure Test

- Old hardcoded `postgresql+asyncpg://nuras@localhost:5432/cashback_e2e_local` removed.
- New uses `_canonical_pg_url()` (env `POSTGRES_E2E_URL`, works with `loyalty/.../cashback_e2e_ci`
  in CI and `nuras/...` locally) and derives bad Redis as
  `redis://127.0.0.1:<unused-port>/<canonical-db>` (closed port → refusal, real server untouched).
- No `nuras`, no fixed local DB, no DB15. `test_cleanup_idempotent_without_setup` same pattern.

## Removal of CLIENT PAUSE

- Deleted `CLIENT PAUSE 3000` (server-wide, affects all logical DBs) from
  `test_pre_one_e2e_real_redis_limiter`. No `PAUSE`/`SHUTDOWN`/flush/firewall/monkeypatch
  in canonical suite (verified `grep -rn PAUSE e2e/*.py` clean after change).

## Isolated Redis Outage Proof

New outage section in `test_pre_one_e2e_real_redis_limiter`:

- Keeps primary keys/readiness proof.
- Starts secondary Uvicorn on `find_free_port()` with same safe PG, `REDIS_URL` =
  `redis://127.0.0.1:<unused-port>/<canonical-db>`, `APP_ENV=development`,
  same production limiter selection, ephemeral secrets, own log/tmp.
- Waits for `/health/live` 200 (no Redis needed, 10s bound), then real
  `POST /auth/challenge` → `503`/`429` fail-closed, `GET /health/ready` → `503`.
- Terminates isolated proc, removes tmp, no shared disturbance.
- Proves real `RedisRateLimiter` in path without pausing/stopping shared Redis.

## Real Redis Limiter Evidence

- Primary: admin login + challenge → `keys rate_limit:* >=1` in dedicated DB,
  `/health/ready` 200. Retained from FIX-A, still passes.
- Outage: isolated backend as above (not mocked limiter). Combined proves Redis in path.

## Normal Run #1

```
./scripts/run_pre_one_e2e.sh
E2E DB target: host=localhost port=5432 database=cashback_e2e_local
E2E Redis target: host=127.0.0.1 port=6379 db=14
30 passed in 28.25s (5 flow + 25 safety)
SUCCESS
```

## Normal Run #2

```
./scripts/run_pre_one_e2e.sh
30 passed in 28.95s
SUCCESS
```

No manual cleanup between.

## Idempotency Regression

Unchanged from FIX-A, re-run passes:

- Fresh-state redelivery of `[card_a,card_a_v2]` + `[tx-001,tx-002]` → Card A 1, T1 1, T2 1.
- Exact PG `==`, non-empty replay requests >0 (2 cards + 2 txs in one batch).

## T3 Regression

Unchanged, passes:

- T3 `tx-003`/`retry-tx-3` via dead `HttpCloudClient(127.0.0.1:18999)` → fail, T3 0, cursors unchanged.
- Retry → T3 1, cursor advances. Fresh replay → still 1.
- Final: Card A 1, Card B 1, T1 1, T2 1, T3 1, B-tx 1.

## Full-flow Privacy

- Full-chain end scans `backend.log` for DB pwd, admin pwd, all keys, agent keys, phones,
  barcodes → 0 leaks (generic assert, no secrets in message).
- `log_privacy` extended same. Runner safe lines only. Markers `fixture-review-*` 0 times.

## Backend Regression

```
cd backend
pytest -v -m "not slow" → 265 passed, 36 skipped
ruff check app tests migrations → All checks passed
mypy app migrations → Success 57 files
python -m compileall → ok
POSTGRES_TEST_URL=... pytest tests/test_postgres_*.py → 36 passed
```

## PostgreSQL Regression

36 passed (concurrency, locks, isolation) as above.

## Admin Regression

```
npm ci, npm test → 44 passed (6 files), typecheck ok, lint ok, build ok (358KB), audit 0 high
```

## Mobile Regression

```
npm ci, npm test → 81 passed (5 suites), typecheck ok, lint ok, export → dist (ios 3.7MB, android 3.8MB)
```

## Agent Regression

```
PYTHONPATH=src pytest → 76 passed, ruff ok, mypy 35 files ok, compileall ok
```

## CI Changes

No CI YAML change needed for FIX-B (already canonical `cashback_e2e_ci` + `/14`).
Safety tests now CI-compatible:

- Derive PG/Redis from env (no `nuras`, no `cashback_e2e_local`, no DB15).
- PG `loyalty` superuser can `CREATEDB` unique owned DBs; else fail (not silent skip).
- No extra DB15 service needed. Redis busy tests use canonical DB only.
- Runner preflight works with CI env (empty fresh service passes).

## Git Ignore / dump.rdb

- Preexisting untracked `dump.rdb` (local Redis persistence) NOT deleted.
- Added narrow `/.gitignore`: `/dump.rdb` (root only, not broad `*.rdb`).
- `git check-ignore -v dump.rdb` → `.gitignore:71:/dump.rdb`. Not committed.
- After commit `git status` clean via ignore.

## Files Changed

- `e2e/preflight.py` (NEW single preflight, env-only, safe output)
- `e2e/harness.py` (`E2ESafetyError`, safe messages, ownership token, token-gated FLUSHDB, no `nuras` default, safe alembic error)
- `e2e/test_resource_safety.py` (rewrite: owned PG/Redis, no DB15/fixed keys, CI-compatible, runner probes, privacy probes)
- `e2e/test_pre_one_flow.py` (isolated outage, no PAUSE, extra imports)
- `scripts/run_pre_one_e2e.sh` (preflight before pytest, no hardcoded dev path/user)
- `.gitignore` (`/dump.rdb`)
- `docs/TASK_013_FIX_B_REPORT.md` (this report)

## Branch

`task-013-fix-b` (from `task-013-fix-a`)

## HEAD

Baseline `625f2ec04a128ca68eac7f968be105f7533660ae`, new pending `fix(e2e): make resource safety tests non-destructive`

## Git Status

Clean (ignored `dump.rdb`) on `task-013-fix-b` after commit.
