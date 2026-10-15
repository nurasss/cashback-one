# TASK-011B Report — Admin Mutations

## Summary

Implemented audited Admin operations for Business create/update, Agent provisioning/key rotation/revocation, durable full-resync requests, and card unbinding. Mutation routes retain the TASK-011A Admin authentication, CSRF/origin, HTTPS, RBAC, and tenant-isolation boundaries. Each successful state change and its audit entry commit in one database transaction.

## Baseline

- Required base branch/HEAD: `task-011-admin` / `4f77d306002b8b9a2dc544a796b5f8cafe7eef27`.
- The initial `/Users/nuras/Desktop/cashback-one` checkout was dirty and detached at an older commit. It was left untouched. The existing TASK-011A worktree was clean at the required HEAD; implementation proceeded in a new worktree at `/Users/nuras/Desktop/cashback-one-task-011b`, on `task-011b-admin-mutations`.
- No prior commit was amended. Agent runtime, Mobile source/lockfile, Stage 0, COM discovery, and ONE mapping were not changed.
- Business status values were confirmed from existing code/tests as `active` and `inactive`. Prefix values remain opaque; this task adds no prefix semantics.

## Scope

Added Cloud Admin mutation APIs and UI plus durable Cloud-side Agent command-request state. No Agent command polling/execution protocol, physical Business delete, arbitrary Admin rebind, customer deletion, or ONE/COM behavior was added.

## Migration

Added `backend/migrations/versions/0009_admin_mutations.py` after `0008_admin_auth`; migration `0008` was not edited. On PostgreSQL, a fresh `alembic upgrade head` reached `0009_admin_mutations`; `alembic downgrade -1` returned to `0008_admin_auth`, and another `upgrade head` reached `0009_admin_mutations`.

The migration adds nullable `audit_log.admin_user_id` and `audit_log.business_id` foreign keys/indexes, preserving legacy rows with NULL scope. It creates `agent_commands` and a partial unique index allowing at most one full-resync command in `pending`/`running` state per Agent.

## Business Mutations

Added superadmin-only `POST /admin/businesses` and `PATCH /admin/businesses/{business_id}`. Names are trimmed and limited to 255 characters; status is restricted to existing `active`/`inactive` values. Logo URLs require HTTPS and reject embedded credentials. Colors are bounded JSON objects (8 KiB, bounded depth and entry counts), while the complete business request body is capped at 16 KiB. `barcode_prefixes` accepts `null` or `[]` and has no inferred barcode rules. Business creation/update and audit entries share one transaction.

## Agent Provisioning

Added superadmin-only `POST /admin/agents` with `{business_id}`. It reuses `issue_agent_key()` and the existing `agk_` format/SHA-256 hash used by `X-Agent-Key` authentication. The database retains only `key_hash`; the successful create response returns `{agent, api_key}` once.

## One-Time Agent Key

Create/rotation responses are no-store and disclose the raw key only in that mutation response. No key-read route exists. The SPA keeps the disclosure in transient component state rather than a query/mutation cache, supports copy only after a user click, and clears key state when the modal closes. If the operator loses the disclosed key, it cannot be fetched; rotate it instead.

## Agent Key Rotation

Added superadmin-only `POST /admin/agents/{agent_id}/rotate-key`. It reuses `rotate_agent_key()` and locks the Agent row before replacing the stored hash. Once committed, the old key fails and only the newly disclosed key remains valid. Non-active Agents return `409 ADMIN_AGENT_REVOKED`. Concurrent PostgreSQL rotations serialize; the last committed key hash is retained.

## Agent Revocation

Added superadmin-only `POST /admin/agents/{agent_id}/revoke`. It reuses `revoke_agent()`, keeps the Agent row/history, and treats repeat revocation as a safe no-op. Existing `X-Agent-Key` authentication rejects a retained key with `403 AGENT_REVOKED` after status changes to `revoked`.

## Full Resync Request

Added superadmin-only `POST /admin/agents/{agent_id}/full-resync`. It durably records an `AgentCommand` and returns `202 {command_id, status: "pending", execution: "deferred"}`. The response does not imply any synchronization ran or completed.

## Resync Concurrency

Requests lock the Agent row and are protected by the PostgreSQL partial unique index for one active full-resync per Agent. Repeated/concurrent requests return the same active command ID and do not create another request audit row. PostgreSQL tests verified one active row and one audit event.

## Card Unbind

Added `POST /admin/cards/{card_id}/unbind`. Superadmins can unbind any card; managers can unbind only a card selected by their authenticated business scope. The endpoint removes only the `UserCard` relation, leaving Card, User, barcode, and balance intact. UI confirmation shows business, masked customer, barcode, and the effect before sending the request.

## Unbind Concurrency

The service locks the scoped Card and its binding row. Concurrent/repeated calls converge on one deletion; later calls return idempotent `{status: "already_unbound"}` without another audit. PostgreSQL tests verified the race, retained Card/User rows, and unchanged balance. No Admin arbitrary rebind is present.

## Audit Schema

`AuditLog` now has nullable `admin_user_id` and `business_id` foreign keys. New events derive actor and tenant from authenticated database rows. Existing audit rows remain unchanged and NULL-scoped.

## Audit Atomicity

Business create/update, Agent create/rotate/revoke, resync request, and unbind add audit rows inside the same transaction as the mutation. A PostgreSQL check-constraint fault test rejected a `business_created` audit insert and verified the Business row rolled back too.

## Audit Tenant Isolation

`GET /admin/audit` permits managers but applies `WHERE audit_log.business_id = authenticated_admin.business_id` in SQL. Superadmins retain global visibility. NULL-scoped legacy rows are invisible to managers. Tests verify own-tenant visibility, exclusion of foreign/legacy entries, and superadmin visibility across tenants.

## Secret Redaction

Audit serialization removes password/token/key/phone/barcode/full-name keys and redacts Agent-key, JWT, refresh-token, and URL query/fragment patterns. Business audit snapshots preserve color keys only and record color-change state, not color values. Card-unbind audit records IDs only. Frontend source tests guard against persistent key storage; the disclosure bypasses query cache, URLs, localStorage, sessionStorage, and IndexedDB.

## Admin Frontend

Extended the SPA with Business create/edit, Agent create/rotate/revoke, confirmed full-resync requests, scoped Card unbind, and tenant-scoped Audit. Manager navigation exposes Audit and own-business unbind, but hides all superadmin mutation controls. Backend RBAC remains authoritative. Key dialogs support copy after a user click, keyboard Escape/tab handling, focus restoration, and key-state clearing on close.

## RBAC

Business and Agent mutation permissions are enforced by both route handlers and services as superadmin-only. Managers cannot create/edit Businesses, create/rotate/revoke Agents, or request resync. Unbind accepts superadmin or manager roles, with the manager business predicate in SQL. Audit filtering uses the authenticated AdminUser and is also SQL-enforced.

## Backend Tests

`APP_ENV=test DATABASE_URL=sqlite+aiosqlite:///:memory: pytest -v -m 'not slow'` — **204 passed, 36 skipped**. The skips are PostgreSQL-specific tests omitted from this invocation; the full PostgreSQL suite was run separately below. Coverage includes Business validation/audit, RBAC, key lifecycle and Agent auth, idempotent deferred resync, secret redaction, audit rollback, and scoped/idempotent unbind.

## PostgreSQL Tests

`POSTGRES_TEST_URL=postgresql+asyncpg:///task011b_regression ... pytest -v tests/test_postgres_*.py` — **36 passed**. The Admin cases include normalized login/role constraints, concurrent refresh, tenant query scope, concurrent Agent rotation, duplicate resync, concurrent unbind, and audit rollback atomicity. Task-specific PostgreSQL scratch databases were removed after validation.

## Agent Regression

From `agent/`, using the available project Python environment: `PYTHONPATH=src pytest -v` — **76 passed**. `ruff check src tests`, `mypy src tests`, and `python -m compileall -q src tests` passed. Agent source/protocol files are unchanged.

## Admin Tests

From `admin/`, `npm ci` succeeded and `npm test -- --reporter=dot` passed **44 tests in 6 files**. Tests cover role controls, Business create/edit validation, one-time key creation/rotation and clearing, revoke/resync confirmation, pending/deferred resync copy, scoped unbind confirmation/refresh, and source guards.

## Admin Build

`npm run typecheck`, `npm run lint`, and `npm run build` passed. Vite emitted the production SPA bundle. `npm audit --audit-level=low` reported **0 vulnerabilities**.

## Mobile Regression

No Mobile source, dependency, or lockfile changes were made. `npm ci` succeeded; `npm test -- --runInBand` passed **81 tests in 5 suites**; `npm run typecheck`, `npm run lint`, and `npm run export` passed, including iOS and Android bundles. An initial install attempt hit `ENOSPC`; it succeeded after removing ignored task-generated npm caches. One initial full suite run hit the existing SMS test’s five-second timeout; the isolated test passed, then the complete suite passed. npm’s install audit reported **15 existing Mobile-tree advisories (11 moderate, 4 high)**; no Mobile audit fixes were applied.

## Ruff

Backend `ruff check app tests migrations` and Agent `ruff check src tests` — **PASS**.

## Mypy

Backend `mypy app migrations` — **PASS**, no issues in 56 source files. Agent `mypy src tests` — **PASS**, no issues in 35 source files.

## Compileall

Backend `python -m compileall -q app tests migrations` and Agent `python -m compileall -q src tests` — **PASS**.

## npm Audit

Admin `npm audit --audit-level=low` — **0 vulnerabilities**. Mobile `npm ci` reported **15 advisories (11 moderate, 4 high)** in its unchanged dependency tree.

## Known Limitations

- Full-resync commands remain pending because no Agent polling/execution contract exists; no ONE/COM details were inferred.
- A pending request is not transitioned if its Agent is later revoked; state transitions require a future Agent worker/protocol.
- A raw Agent key cannot be recovered after its one-time create/rotate response is lost or the dialog closes; rotate it to issue another key.
- Legacy AuditLog entries without `business_id` remain superadmin-only.
- Mobile dependency advisories remain in the unchanged lockfile. No production deployment was performed.

## Deferred Work

Agent command polling/execution and completion/error transitions; physical Business deletion; arbitrary Admin rebind; customer deletion; Real ONE mapping, OneLoyaltySource, COM discovery; deployment; marketing, push, news, Wallet passes, and billing remain deferred.

## Files Changed

- Migration: `backend/migrations/versions/0009_admin_mutations.py`.
- Backend: `backend/app/api/admin.py`, `backend/app/main.py`, `backend/app/core/request_limits.py`, `backend/app/models/{__init__,admin,entities}.py`, `backend/app/schemas/admin.py`, `backend/app/services/{admin_mutations,admin_queries}.py`.
- Backend tests: `backend/tests/test_admin_mutations.py`; updates to `backend/tests/test_admin_mvp.py` and `backend/tests/test_postgres_admin_security.py`.
- Admin app: `admin/src/api/{client,errors,types}.ts`, `admin/src/auth/security.test.tsx`, `admin/src/features/{Navigation,AdminMutations}.tsx`, `admin/src/layout/AppRouter.tsx`, `admin/src/pages/{AgentsPage,AuditPage,BusinessesPage,OperationsPage}.tsx`, `admin/src/styles/admin.css`.
- Admin tests: `admin/tests/mutations.test.tsx`; update to `admin/tests/navigation.test.tsx`.
- Documentation: `admin/README.md`, `docs/ADMIN_API.md`, and this report.
- No tracked `agent/` or `mobile/` files changed.

## Branch

`task-011b-admin-mutations`.

## HEAD

This report is part of the commit, so its own hash cannot be embedded without changing that hash. The required base was `4f77d306002b8b9a2dc544a796b5f8cafe7eef27`; the final commit HEAD is supplied in the handoff.

## Git Status

Post-commit status is verified clean; exact output is supplied in the handoff.
