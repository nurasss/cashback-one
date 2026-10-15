# TASK-013 FIX-A Report: E2E Resource Safety, Real Redis Boundary & Exactly-Once Proof

Date: 2026-10-03
Branch: `task-013-fix-a`
Baseline branch: `task-013-pre-one-e2e`
Baseline HEAD: `e02b6fb6c72b8ad3a031683d0347bd92ac8b501e`
New HEAD: pending commit on `task-013-fix-a` (see `git rev-parse HEAD` after commit)
Git Status: clean (after commit)

## Summary

Narrow FIX-A over TASK-013. No harness rewrite, no product behavior change except
hardening, no ONE/COM/Stage0 touch, no production test bypass.

- DB target uses `sqlalchemy.engine.make_url` structural parsing, rejects query
  overrides, enforces `cashback_e2e_` strict prefix, verifies `SELECT current_database()`
  before any migration/TRUNCATE, requires verified immutable state for destructive ops.
- Redis single source `REDIS_URL`, rejects DB0/missing/query/remote, requires empty
  dedicated DB before run, FLUSHDB only on verified same target, uses configured DB exactly.
- Backend runs in `development` with ephemeral secrets; `get_rate_limiter` is Redis-only
  (InMemory only via explicit unit-test `dependency_overrides`). E2E proves keys in Redis
  and fail-closed outage.
- Exactly-once via real redelivery of same non-empty batch through production
  `AgentRuntime`+`HttpCloudClient` with stable IDs and exact PostgreSQL counts.
  T3 failure/retry/replay with real HTTP failure (connection refused) and cursor evidence.
- Runner never prints URLs/passwords/tokens; safe host/port/name only via Python helper.
  Full-flow privacy scan passes.
- Fixture lifecycle fixed (`try: setup(); yield; finally: cleanup()`), cleanup idempotent
  and partial-init safe. Setup-failure + unavailable-Redis regression passes.
- CI uses `cashback_e2e_ci` + dedicated Redis 14, same `REDIS_URL`, ephemeral secrets,
  no echo. Canonical `./scripts/run_pre_one_e2e.sh` Run#1 PASS, Run#2 PASS.
- Guard probes: unsafe DB and Redis DB0 refuse, sentinels survive.

## Baseline

- Branch before: `task-013-pre-one-e2e`
- HEAD before: `e02b6fb6c72b8ad3a031683d0347bd92ac8b501e`
- `git status` clean in worktree `/Users/nuras/Desktop/cashback-one-task-011b`
- Created `git switch -c task-013-fix-a` (no amend of baseline).
- Verified foundation preserved: real PG, real Uvicorn, real AgentRuntime/HttpCloudClient,
  admin auth/API, business/agent provisioning, heartbeat, card sync, T1/T2 sync, customer
  auth, auto-binding, wallet/history, tenant/manager isolation, revoke, rotation,
  full-resync pending, no guessed ONE metadata, TestLoyaltySource not production-selectable,
  no external Wappi/SMS/ONE calls.

## Database Safety Root Cause

Old guard used `"test" in db_name` substring on `urlparse().path`:

- `latest` / `contest` contain `test` as substring → allowed non-test DB.
- `postgresql+asyncpg://.../e2e_test?database=production` path looks safe but query
  override selects `production`; harness then ran migrations/TRUNCATE. Unacceptable.

## Database Target Validation

`e2e/harness.py`:

- `validate_e2e_db_url()` uses `make_url`, requires driver `postgresql+asyncpg`,
  explicit DB matching `^cashback_e2e_[a-z0-9_]{1,32}$` (max 63), empty `query` dict
  (rejects `?database=`, `?dbname=`, `?host=`, `?port=`, `?service=`, `?options=`, any),
  host allowlist `{localhost,127.0.0.1,::1,postgres}`, rejects `APP_ENV=production`.
- `E2E_DB_PREFIX=cashback_e2e_`, `DEFAULT_E2E_DB_URL=.../cashback_e2e_local`.
- `safe_db_info()` returns host/port/database/driver only (no user/password).
- Runner validates via Python helper before pytest and prints only safe components.

Tests (`e2e/test_resource_safety.py`):

- `latest`, `contest`, `production`, `task_latest`, `contest_db` → reject.
- `cashback_e2e_abc123?database=production` → reject.
- `cashback_e2e_abc123`, `cashback_e2e_ci` → allow.
- Remote host → reject.

## Actual current_database Verification

- `E2EHarness._verify_actual_database()` connects and runs `SELECT current_database()`
  BEFORE migrations/TRUNCATE. Requires exact match with `parsed.database` and prefix match.
  On mismatch ABORT. Sets immutable `_database_verified`, `_verified_db_name/host/port`.
- `clean_database_tables()` and `_run_alembic_migrations()` require `_database_verified`.
- `setup()` order: verify DB → verify Redis empty → migrations → engine → truncate
  → bootstrap → start backend.

## Redis Safety Root Cause

- Runner declared `REDIS_URL=/14`, `E2EConfig` defaulted `/15` and overwrote env →
  two sources, harness/backend/cleanup could diverge.
- `_verify_and_flush_redis()` did unconditional `FLUSHDB` on configured URL (arbitrary DB).

## Redis Target Validation

- Single source `REDIS_URL` (supports `REDIS_E2E_URL` only if equal, else abort on conflict).
  `E2EConfig.__post_init__` resolves and validates eagerly. Default `/14`.
- `validate_redis_url()` requires scheme `redis`, host allowlist
  `{localhost,127.0.0.1,::1,redis,postgres}`, path `/<db>` 1..15 (DB0 rejected,
  missing/invalid/query rejected).
- `safe_redis_info()` returns host/port/db only.

## Redis Cleanup Model

- `_verify_redis_dedicated_empty()`: ping, `DBSIZE==0` else REFUSE (never deletes).
  Marks `_redis_verified/_redis_dedicated` + verified host/port/db.
- `cleanup()/teardown()` idempotent: guards `if resource is not None`, bounded
  terminate/kill, engine dispose, Redis `FLUSHDB` ONLY if dedicated and current
  `host/port/db` still equals verified target, temp dir removal safe.
- `teardown()` alias to `cleanup()` for backward compat.

## Real Redis Rate Limiter

- Harness sets `APP_ENV=development` (constant `E2E_APP_ENV`) with ephemeral
  `secrets.token_hex(32)` keys, `WHATSAPP_LOGIN_NUMBER=+77001234567`,
  `ADMIN_ALLOW_INSECURE_HTTP=true`, `SMS_PROVIDER_MODE=disabled`, etc.
- `backend/app/services/rate_limiter.py`: removed `if app_env==test: return _test_limiter`.
  `get_rate_limiter()` always Redis-backed via `app.state.redis` or shared client.
  `InMemoryRateLimiter` docstring restricted to explicit unit-test injection.
  No `E2E_BYPASS_SECURITY` / `USE_FAKE_REDIS` / `FORCE_TEST_AUTH` added. Production remains Redis.
- `backend/tests/conftest.py`: autouse `_inject_test_limiter` + `client` fixture inject
  `_test_limiter` via `dependency_overrides`; `test_admin_mvp/mutations` fixtures updated.
  Unit tests retain determinism without production switch.

## Redis Runtime Evidence

New `test_pre_one_e2e_real_redis_limiter`:

- Asserts `APP_ENV=development`.
- Admin login + `/auth/challenge` via real HTTP.
- `redis_rate_limit_key_count()` (`keys rate_limit:*` on dedicated DB) `>=1` → auth touches Redis.
- `/health/ready` 200 when healthy.
- `CLIENT PAUSE 3000` (real outage, auto-recovers), then `/auth/challenge` must be
  fail-closed `503` (or `429`), not `200` memory fallback. Verified `503` locally.
- After 3.5s, `/health/ready` 200 again. Readiness 503 during outage also covered.

## Idempotent Redelivery

`test_pre_one_e2e_full_chain` §9:

- After T1/T2 exact counts, same-runtime empty cycle still exact (legacy).
- Fresh `StateStore(agent_a_redeliver.sqlite3)` + same Cloud agent/key + new
  `TestLoyaltySource(cards=[card_a,card_a_v2], transactions=[tx_1,tx_2])` (stable
  `barcode`/`external_id`) through production `AgentRuntime`+`HttpCloudClient`.
- Exact PG counts unchanged (see below). Proves server idempotency, not cursor skip.

Stable IDs: `barcode_a=0123456789012`, `tx-001`, `tx-002`, `tx-003`, `tx-b-001`,
`retry-tx-*`; backend upserts cards by `(business_id,barcode)` and dedupes
transactions by `(card_id,external_id)`.

## Exact PostgreSQL Counts

Direct PG via `harness._sessionmaker` (`SELECT COUNT(*)`), exact `==`, never `>=`:

- After T1: Card A 1, tx-001 1.
- After T2: Card A 1, tx-001 1, tx-002 1, CardA-txs 2.
- After redelivery: same exact.
- After T3 retry: Card A 1, tx-001 1, tx-002 1, tx-003 1, CardA-txs 3.
- After T3 replay: same exact.
- Final: Card A 1, T1 1, T2 1, T3 1, Card B 1, tx-b-001 1; Business B separate.
- Retry suite: `retry-tx-1/2/3` each 1, card 1.

## T3 Failure

Full chain §9b and retry suite:

1. Successful T1/T2 state.
2. Add T3 (`tx-003` / `retry-tx-3`).
3. Persist cursors (`get_cursor("cards"/"transactions")`).
4. `HttpCloudClient(base_url=http://127.0.0.1:18999)` → real httpx connection refused
   → `CloudRetryableError` after entering HTTP path (not mocked `sync_transactions`).
5. `sync_cycle()` raises.
6. PG T3 count `==0`.
7. Cursors unchanged (`==` before).

## T3 Retry

- Restore original `HttpCloudClient`, `sync_cycle()` succeeds.
- T3 count `==1`, Card `==1`, cursor advances (`!=` before).

## T3 Replay

- Fresh state DB + same stable source (`[tx_1,tx_2,tx_3]`) via production runtime.
- T3 count still `==1`, all T1/T2/T3 `==1`. Proves Cloud idempotency.

## Agent Cursor Evidence

- Uses real `StateStore.get_cursor/commit_cursor` (SQLite WAL).
- Failed delivery: both `cards` and `transactions` cursors unchanged.
- Successful ACK: `transactions` cursor advances.
- Restart test: fresh `StateStore(same db)` reloads `cards` cursor `==`, second cycle no advance.
- No invented fields.

## Runner Log Privacy

`scripts/run_pre_one_e2e.sh` FIX-A:

- Removed `echo "Database target: ${POSTGRES_E2E_URL}"` and `echo ... ${REDIS_URL}`.
- Validates via Python `safe_db_info/safe_redis_info`, prints
  `E2E DB target: host=... port=... database=...` and
  `E2E Redis target: host=... port=... db=...` only. Raw URL, username, password never emitted.
- Detects conflicting `REDIS_URL` vs `REDIS_E2E_URL`.
- Manual probe with `supersecretpw123` in URL: output contained only safe components,
  password absent.

## Full-Flow Privacy Scan

- Full chain end scans `backend.log` via `scan_logs_for_secrets()` with markers:
  DB password (parsed via `make_url`, not logged), admin password, all signing/hash keys,
  wappi secret, agent keys (old/new/B), phones, barcodes.
- Asserts `not leaks` with generic message (no secret in failure output).
- Passes because backend `redact_sensitive_text` redacts credentials/tokens/phones/barcodes
  and access logs use route templates.
- `test_pre_one_e2e_log_privacy` extended to include DB password + all keys.

## Setup Failure Cleanup

- `e2e/conftest.py` fixed to:
  ```python
  harness = E2EHarness()
  try:
      await harness.setup()
      yield harness
  finally:
      await harness.cleanup()
  ```
  (`finally` runs even if `setup()` raises after partial alloc).
- `E2EHarness.cleanup()` handles `None` engine/proc/log/tmp, bounded terminate.
- Tests: `test_setup_failure_triggers_cleanup_and_idempotent` (temp dir + unavailable
  Redis `6399` → `setup()` raises, `cleanup()` removes tmp, `_engine None`, `_proc None`,
  double cleanup safe) and `test_cleanup_idempotent_without_setup` pass.
- Reviewer temp-dir leak regression covered.

## Cleanup Idempotency

- Double/triple `cleanup()` safe, no destruction of unrelated DBs (Redis flush only on
  verified same target, DB truncate requires verified flag).
- `test_harness_uses_configured_redis_db_exactly` proves `/14` uses 14, not 15 (sentinel in 15 survives).

## CI Changes

`.github/workflows/ci.yml` `pre-one-e2e`:

- `POSTGRES_DB: cashback_e2e_ci` (was `poscenter_loyalty_test`).
- `POSTGRES_E2E_URL: .../cashback_e2e_ci` (canonical prefix).
- `REDIS_URL: redis://127.0.0.1:6379/14` unchanged (dedicated non-zero, single source).
- No `REDIS_E2E_URL` conflict. Redis service starts empty (fresh service); harness refuses if non-empty.
- Secrets ephemeral (harness `secrets.token_hex`), never echoed or artifacted.

## Run #1

```
./scripts/run_pre_one_e2e.sh
E2E DB target: host=localhost port=5432 database=cashback_e2e_local
E2E Redis target: host=127.0.0.1 port=6379 db=14
23 passed in 48.76s
SUCCESS
```

- 5 flow (`full_chain`, `retry_and_cursor_safety`, `real_redis_limiter`, `agent_restart`, `log_privacy`)
- 18 safety (DB/Redis validation, sentinel, cleanup, privacy display)
- No manual DB/Redis cleanup between runs (harness truncates + dedicated flush).

## Run #2

```
./scripts/run_pre_one_e2e.sh
23 passed in 41.68s
SUCCESS
```

Consecutive determinism verified, no manual intervention.

## Backend Regression

```
cd backend
pytest -v -m "not slow" → 265 passed, 36 skipped
ruff check app tests migrations → All checks passed
mypy app migrations → Success 57 files
python -m compileall app tests migrations → ok
```

## PostgreSQL Regression

```
POSTGRES_TEST_URL=... pytest -v tests/test_postgres_*.py → 36 passed
```

## Admin Regression

```
cd admin
npm ci → ok
npm test → 44 passed (6 files)
npm run typecheck → ok
npm run lint → ok
npm run build → ok (358KB JS)
npm audit --audit-level=high → 0 vulnerabilities
```

## Mobile Regression

```
cd mobile
npm ci → ok
npm test → 81 passed (5 suites)
npm run typecheck → ok
npm run lint → ok
npm run export → Exported: dist (ios 3.7MB, android 3.8MB)
```

## Agent Regression

```
cd agent
PYTHONPATH=src pytest -v → 76 passed
ruff check src tests → All checks passed
mypy src tests → Success 35 files
python -m compileall src tests → ok
```

## Deferred ONE Boundaries

Preserved, no discovery started:

```ini
REAL_WINDOWS_SERVICE = NOT VERIFIED
REAL_V83_COMCONNECTOR = NOT VERIFIED
REAL_ONE_CONNECTION = NOT VERIFIED
REAL_ONE_METADATA_DISCOVERY = NOT VERIFIED
REAL_ONE_MAPPING = NOT VERIFIED
```

- `TestLoyaltySource` remains in `e2e/source.py` only, never imported by production.
- No `/e2e`, `/test` routes, no fake source factory in production, no auth bypass,
  no memory limiter production switch (removed test shortcut; production Redis-only).
- External Wappi/SMS/ONE not called (Wappi webhook simulated inbound with HMAC,
  SMS disabled, ONE stub).

## Files Changed

- `e2e/harness.py` (structural DB/Redis validation, current_database verify, dedicated-empty Redis, development mode, idempotent cleanup)
- `e2e/conftest.py` (setup-failure cleanup lifecycle)
- `e2e/test_pre_one_flow.py` (real redelivery, T3 failure/retry/replay, exact PG counts, real Redis proof, full-flow privacy)
- `e2e/test_resource_safety.py` (new: DB/Redis rejects, sentinel survival, configured DB exact, setup-failure/idempotent, safe display)
- `scripts/run_pre_one_e2e.sh` (safe display, single REDIS_URL, canonical prefix, runs both suites)
- `backend/app/services/rate_limiter.py` (Redis-only runtime, InMemory explicit-test-only)
- `backend/tests/conftest.py` (autouse InMemory injection)
- `backend/tests/test_admin_mvp.py`, `test_admin_mutations.py` (explicit limiter injection)
- `.github/workflows/ci.yml` (canonical `cashback_e2e_ci`, dedicated Redis 14)
- `docs/PRE_ONE_E2E.md` (canonical prerequisites)
- `docs/TASK_013_FIX_A_REPORT.md` (this report)

## Branch

- `task-013-fix-a` (from `task-013-pre-one-e2e`)

## HEAD

- Baseline: `e02b6fb6c72b8ad3a031683d0347bd92ac8b501e`
- New: pending commit `fix(e2e): harden resource safety and prove exactly-once sync` on `task-013-fix-a`

## Git Status

- After commit: clean worktree on `task-013-fix-a` (`git status --porcelain` empty).
