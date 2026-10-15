# TASK-011A Report — Admin MVP Foundation

## Summary

Implemented a read-only Admin SPA and a separate FastAPI Admin security boundary. Admin authentication uses dedicated administrator and refresh-session records, Argon2id password hashes, distinct short-lived Admin JWTs, an HttpOnly refresh cookie, login throttling, central role checks, and SQL-scoped business-manager queries. Dashboard, business, agent, card/user search, and superadmin-only audit views are available. No administrative mutation endpoints or controls were added.

## Baseline

- Required base: `task-010-mobile`, `36d63a3c71575025e74c1b8a5e6adeff34a7aee7`.
- The original checkout had an unrelated untracked APK, so it was left untouched and a separate clean worktree was created at `/Users/nuras/Desktop/cashback-one-task-011` from the required commit.
- Work was done on `task-011-admin`; no existing accepted commit was amended.
- TZ alignment: the Admin role, business fields, agent health fields, barcode/phone lookup, audit view, and statistics follow section 4.4. The task-defined “unblocked” label is used because the source model does not define “active card.”

## Scope

Read-only Admin foundation only. No Stage 0, Agent key management, resync, business editing, card unbinding, user deletion, campaigns, or Wallet passes were implemented.

## Database Migration

Added `backend/migrations/versions/0008_admin_auth.py` after `0007_sms_auth_core`. It creates `admin_users` and `admin_sessions` with login uniqueness, role/business CHECK, business and administrator foreign keys, hashed refresh-token uniqueness, and session indexes. Existing migrations were not edited. On a disposable PostgreSQL database, a fresh `alembic upgrade head` reached `0008_admin_auth`; `alembic downgrade -1` and `alembic upgrade head` both succeeded, and `alembic current` reported `0008_admin_auth (head)`.

## AdminUser

`AdminUser` is separate from customer `User`. Its role is constrained to `superadmin` or `business_manager`; superadmins require a null `business_id`, and managers require a business. Login input is stripped and lowercased, constrained to an ASCII login alphabet, and protected by a database unique constraint. Password hashes are never included in Admin response schemas.

## AdminSession

`AdminSession` stores only a SHA-256 digest of an opaque, randomly generated refresh token, with creation, expiry, revocation, and rotation timestamps. It is separate from customer `AuthSession`.

## Password Security

Passwords have a 12-character minimum and a 1,024-byte maximum. Argon2id is configured with three iterations, 64 MiB memory, and parallelism four. Verification runs off the async event loop; unknown logins use a cached dummy Argon2id hash so they follow the password-verification path. The CLI reads passwords using a hidden `getpass` prompt and never accepts them as command arguments.

## Admin JWT Boundary

Admin access JWTs use a required `ADMIN_JWT_SIGNING_KEY` distinct from the customer key, issuer/audience `cashback-one-admin`, and `typ=admin_access`. The default access lifetime is 900 seconds; the configurable maximum is one hour. Access authentication also checks the active Admin row and session in the database. Tests verify customer tokens are rejected from Admin routes and Admin tokens are rejected from customer routes.

## Refresh Rotation

The refresh token is sent only in an HttpOnly, SameSite=Lax cookie scoped to `/admin`; it is never returned in JSON or exposed to the SPA. Cookies are Secure unless an explicitly enabled development HTTP request is in use. Refresh uses a conditional SQL update as compare-and-swap; PostgreSQL concurrency testing confirmed that two refreshes with one token yield exactly one winner. Logout revokes the current session and expires the cookie.

## Login Rate Limiting

Login attempts are limited by normalized login and source IP using the existing Redis rate limiter. Defaults are five attempts per login and 20 per IP per 300 seconds; these values are configurable. Redis errors fail closed using the existing safe 503 error path. Rate-limit Redis keys contain HMAC fingerprints, not raw login or IP values.

## Superadmin Bootstrap

There is no seeded or default administrator. Run `python -m app.cli.create_admin` from `backend/` after applying migrations and configuring the database. The interactive command requests login, hidden password confirmation, role, and a business UUID for a manager, validates that business, normalizes the login, and stores only an Argon2id hash.

## RBAC

`AdminScope` centralizes the superadmin check and selected-business policy. Managers cannot request a different business; a foreign business selector or inaccessible record resolves to the consistent 404 policy. Business enumeration and global audit require superadmin. Frontend role-aware navigation mirrors these policies, while backend authorization remains authoritative.

## Tenant Isolation

Manager business scope is derived from the authenticated `AdminUser.business_id`, not query or request-body data. Agent, card, user, transaction, and dashboard queries carry tenant predicates in SQL. User searches require an exact normalized phone and a card in scope; user details return only scoped cards. SQLite API/service tests and PostgreSQL query tests cover foreign agent/card/user/statistics visibility and selector rejection.

## Dashboard API

`GET /admin/dashboard` returns distinct active user profiles associated with business cards, cards, unblocked cards (`is_blocked = false`), transactions for a timezone-aware inclusive `from`/`to` period, and server-calculated agent health counts. Periods are ordered and limited by `ADMIN_MAX_STATS_PERIOD_DAYS` (default 90). “Active card” remains undefined in the source model, so the UI and API say “unblocked.”

## Businesses API

Superadmins can page through `GET /admin/businesses` and read `GET /admin/businesses/{business_id}`. Responses expose only configured name, logo URL, colors, prefixes, status, timestamps, and read-only card/customer/agent counts. Managers cannot enumerate businesses. The SPA renders logo URLs only as HTTPS or same-origin images and keeps colors as text.

## Agents API

`GET /admin/agents` and `GET /admin/agents/{agent_id}` return status, health, version, last-seen/sync timestamps, and sanitized error text. Health uses the configurable `ADMIN_AGENT_STALE_SECONDS` threshold (default 900). Agent key hashes and raw keys are not selected or serialized.

## Cards Search

`POST /admin/cards/search` accepts an exact 13-digit barcode string and/or a phone normalized by the existing backend `normalize_phone` function. At least one filter is required; barcode leading zeros are preserved. Search criteria are in JSON request bodies, not URLs. Results are bounded and stably ordered; card phone values are masked.

## Users Search

`POST /admin/users/search` requires a phone and uses the same backend phone normalizer. Managers can find a profile only through a card belonging to their business. List results mask phone numbers; detail reveals the profile phone only when the user has a card in the requesting scope, and includes only cards in that scope.

## Audit

`GET /admin/audit` is superadmin-only, paginated, and ordered by timestamp plus ID. It returns actor, action, entity, and timestamp. `AuditLog` has no structural business key, so manager access is disabled and before/after JSON is omitted rather than guessed or rendered.

## Admin Frontend

Created `admin/` as a Vite, React 19, strict TypeScript SPA with React Router, TanStack Query, Vitest, and React Testing Library. It includes login, dashboard, business detail/list, agents, card and user search/detail, audit, role-aware navigation, bounded tables, retryable errors, empty states, and a responsive desktop-first layout. The build uses only Cloud Backend Admin routes.

## Session Bootstrap

The SPA starts in a loading state, calls `POST /admin/auth/refresh` with browser credentials, then calls `GET /admin/me`. It renders neither a login flash nor authenticated routes before bootstrap completes. A `401` triggers a single-flight refresh and one retry; failed refresh clears the in-memory session and query cache. A `403` remains an access error and does not log the user out.

## Frontend Token Security

Access JWTs live only in the `AdminSession` JavaScript object. Refresh tokens stay in the HttpOnly cookie. A source-guard test prevents `localStorage`, `sessionStorage`, or IndexedDB token storage. API errors retain safe machine codes only; response messages and request bodies are not logged or shown directly.

## CORS

`ADMIN_ALLOWED_ORIGINS` is validated as a list of exact HTTP(S) origins; wildcard origins, paths, credentials, and duplicates are rejected. Credentialed CORS uses this allowlist and permits the Admin request header needed for CSRF protection. Admin routes require an allowlisted `Origin` and `X-Admin-Request: 1`. Production rejects HTTP origins. No `*` plus credentials configuration is used.

## Transport Security

`VITE_API_BASE_URL` is required, centrally validated as an absolute URL, and has trailing slashes normalized. HTTPS is always required for production builds. HTTP requires both Vite development mode and `VITE_ALLOW_INSECURE_HTTP=1`; backend HTTP requires `APP_ENV=development`, `ADMIN_ALLOW_INSECURE_HTTP=1`, and an explicitly allowlisted development origin. Invalid configuration returns safe machine errors. Production reverse proxies must pass the trusted external HTTPS scheme to ASGI; deployment response headers and proxy trust are documented in `admin/README.md`.

## Accessibility

Login and search inputs have semantic labels; forms, buttons, tabs, navigation, errors, and tables expose accessible roles and names. Keyboard focus is visible and touch/click targets are sized for use. Errors use text and icons as well as color.

## XSS Protection

Stored business, agent, card, and audit values are rendered as text. The SPA does not use `dangerouslySetInnerHTML`. HTTPS/same-origin logo sources are rendered as images with `referrerPolicy="no-referrer"`; raw HTML and API error text are not interpreted.

## Backend Tests

`APP_ENV=test DATABASE_URL=sqlite+aiosqlite:///:memory: .venv/bin/pytest -v -m 'not slow'` — **198 passed, 31 skipped**. The skips are the PostgreSQL-specific tests when `POSTGRES_TEST_URL` is absent from this run; those tests were run separately below. Admin tests cover password hashing and generic failures, inactive/expired sessions, cookie lifecycle, refresh rotation/replay, token separation, rate limiting, CSRF/origin policy, role restrictions, tenant scope, search validation/normalization, dashboard counts, audit, and sanitized errors.

## PostgreSQL Tests

`POSTGRES_TEST_URL=postgresql+asyncpg:///task011a_regression APP_ENV=test DATABASE_URL=sqlite+aiosqlite:///:memory: .venv/bin/pytest -v tests/test_postgres_*.py` — **32 passed** on the available local PostgreSQL server. The added Admin cases cover normalized-login uniqueness, the role/business invariant, concurrent refresh rotation, and SQL tenant scoping. Both disposable databases used for the test run and migration checks were created specifically for this task and removed afterward.

## Admin Tests

From `admin/`: `npm ci` succeeded; `npm test -- --reporter=dot` — **38 passed in 5 files**. The suite covers bootstrap loading, login errors, token storage guard, 401 refresh/retry and failure, logout, role navigation, API transport validation and privacy-safe rendering.

## Admin Build

From `admin/`: `npm run typecheck`, `npm run lint`, and `npm run build` all succeeded. The Vite production build emitted static JS/CSS assets. `npm audit --audit-level=low` reported **0 vulnerabilities** for Admin dependencies.

## Mobile Regression

No Mobile source, dependency, or lockfile changes were made. From `mobile/`, `npm ci` succeeded, `npm test -- --runInBand` passed **81 tests in 5 suites**, `npm run typecheck` passed, `npm run lint` passed, and `npm run export` successfully exported iOS and Android bundles. The first test attempt ran concurrently with Metro export and hit one test’s five-second timeout; the serialized rerun passed. During Mobile `npm ci`, npm reported 15 existing dependency audit findings (11 moderate, 4 high); no Mobile dependency changes or forced audit fixes were made in this Admin-only task.

## Ruff

`backend/.venv/bin/ruff check app tests migrations` — **PASS** (all checks passed).

## Mypy

`backend/.venv/bin/mypy app migrations` — **PASS**, no issues found in 53 source files.

## Compileall

`python3 -m compileall -q app tests migrations` from `backend/` — **PASS**.

## npm Audit

Admin: `npm audit --audit-level=low` — **0 vulnerabilities**. Mobile install audit output: **15 findings (11 moderate, 4 high)** in its unchanged dependency tree, as recorded under Mobile Regression.

## Known Limitations

- The business meaning of “active card” is not defined in the model; only `unblocked_cards` is reported.
- Global `AuditLog` rows cannot be tenant-scoped with the current model; managers are denied access and audit state JSON is omitted.
- Live production credentials/backend and reverse-proxy deployment were not available for an end-to-end deployed-browser session. No administrator account was created; use the documented bootstrap CLI after deployment.
- TLS termination must preserve the trusted external scheme at the ASGI boundary. Different-site SPA/API hosting must also account for browser third-party-cookie restrictions; same-site HTTPS origins are the intended deployment.
- Mobile npm reported existing lockfile dependency advisories; Mobile is outside this task’s change scope.

## Deferred Admin Mutations

Agent creation/key issue/rotation/revocation, full resync, business editing/deletion, card unbinding/rebinding, customer deletion, and other mutation workflows remain deferred to TASK-011B.

## Files Changed

- Root config: `.env.example`.
- Admin app: `admin/package.json`, `admin/package-lock.json`, Vite/TypeScript/ESLint config, `admin/.env.example`, `admin/README.md`, all `admin/src/` modules, and four frontend test files under `admin/tests/`.
- Backend Admin implementation: `backend/app/api/admin*.py`, `backend/app/cli/`, `backend/app/core/admin_types.py`, `backend/app/models/admin.py`, `backend/app/schemas/admin.py`, and `backend/app/services/admin_{auth,queries,security}.py`.
- Backend integration/config: `backend/app/core/config.py`, `backend/app/main.py`, `backend/app/models/__init__.py`, `backend/app/services/rate_limiter.py`, `backend/pyproject.toml`, `backend/requirements.txt`, and `backend/tests/test_config.py`.
- Migration and tests: `backend/migrations/versions/0008_admin_auth.py`, `backend/tests/test_admin_{cli,config,mvp}.py`, `backend/tests/test_postgres_admin_security.py`.
- Docs: `docs/ADMIN_API.md` and this report.

## Branch

`task-011-admin`.

## HEAD

The report is included in the commit, so its own final commit hash cannot be embedded without changing that hash. The required base HEAD was `36d63a3c71575025e74c1b8a5e6adeff34a7aee7`; the resulting commit HEAD is provided in the final handoff.

## Git Status

The final post-commit `git status` was checked and is clean; exact output is provided in the final handoff.
