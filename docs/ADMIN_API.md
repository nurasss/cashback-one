# Admin API — TASK-011A/011B

Admin routes are separate from `/auth/*`, `/me/*` and `/agent/*`. All responses containing Admin state use `Cache-Control: no-store`. Browser requests must have an exact configured `Origin` and `X-Admin-Request: 1`. Credentialed CORS is allowlist-only. Every Admin request also requires HTTPS except an explicitly enabled development request in `APP_ENV=development`.

## Authentication

| Endpoint | Method | Request | Authentication | Success |
|---|---|---|---|---|
| `/admin/auth/login` | POST | `{ "login": "…", "password": "…" }` | allowlisted Origin + CSRF header | `200 {access_token, token_type, expires_in}`; refresh in HttpOnly cookie only |
| `/admin/auth/refresh` | POST | `{}` | allowlisted Origin + CSRF header + `admin_refresh` HttpOnly cookie | rotates stored refresh hash and cookie, returns a new access JWT |
| `/admin/auth/logout` | POST | `{}` | allowlisted Origin + CSRF header + current refresh cookie | `200 {status: "ok"}`; revokes current session and expires the cookie |
| `/admin/me` | GET | — | `typ=admin_access` Bearer token and active DB session | `{admin: {id, login, role, business}}` |

Invalid login, password and inactive-account cases all return `401 INVALID_CREDENTIALS`. No registration or default user endpoint exists. Invalid/expired/replayed refresh cookies return the same `401 ADMIN_UNAUTHENTICATED` response. Refresh rotation uses an atomic compare-and-swap on the old refresh hash; simultaneous requests have at most one winner.

## Read-only data

| Endpoint | Method | Important parameters/body | Roles |
|---|---|---|---|
| `/admin/dashboard` | GET | optional `business_id`, `from`, `to` ISO timestamps | Superadmin may filter; manager is fixed to own business |
| `/admin/businesses` | GET | `limit` 1–100, `offset` ≤100,000 | Superadmin only |
| `/admin/businesses/{business_id}` | GET | UUID | Superadmin only |
| `/admin/agents` | GET | `limit`, `offset`, optional `business_id` | Manager SQL-scoped to own business |
| `/admin/agents/{agent_id}` | GET | UUID | Manager receives own-business rows only |
| `/admin/cards/search` | POST | `{barcode?, phone?, business_id?}`, `limit`, `offset` | Manager SQL-scoped to own business |
| `/admin/cards/{card_id}` | GET | UUID | Manager receives own-business rows only |
| `/admin/users/search` | POST | `{phone, business_id?}`, `limit`, `offset` | Manager's users must be linked to own-business card(s) |
| `/admin/users/{user_id}` | GET | UUID, optional tenant selector and page | Manager sees only own-business card details |
| `/admin/audit` | GET | `limit`, `offset` | Superadmin sees all; manager SQL-scoped to own `business_id`; legacy NULL-scoped rows hidden |

All list rows sort by a stable timestamp and ID tie-breaker. `Page<T>` is `{items, limit, offset, has_more}`; clients fetch another bounded page only when `has_more` is true.

Dashboard period timestamps must include a timezone, `from <= to`, and the range may not exceed `ADMIN_MAX_STATS_PERIOD_DAYS`. Values are compared in UTC. Customer count means distinct active profiles linked to a card in that business. “Unblocked cards” is exactly `is_blocked = false`. Agent health is calculated by the backend: `disabled`, `error`, `never_connected`, `stale`, or `online`; stale seconds come from `ADMIN_AGENT_STALE_SECONDS` (default 900). No API key hash is returned. Sensitive search values arrive in POST JSON and are not written to request/application logs.

`business_manager` scope always comes from the authenticated AdminUser row. A foreign tenant selector and foreign IDs return a uniform `404 ADMIN_RESOURCE_NOT_FOUND`; global businesses return `403 ADMIN_FORBIDDEN` without querying other-tenant payload rows.

## Error envelope

Errors use the existing `{ "error": { "code": "…", "message": "…" } }` contract. Admin additions include `INVALID_CREDENTIALS`, `ADMIN_UNAUTHENTICATED`, `ADMIN_FORBIDDEN`, `ADMIN_RESOURCE_NOT_FOUND`, `ADMIN_RATE_LIMITED`, `ADMIN_ORIGIN_FORBIDDEN`, `ADMIN_CSRF_BLOCKED`, `ADMIN_HTTPS_REQUIRED`, `ADMIN_INVALID_PERIOD`, `ADMIN_PERIOD_TOO_LARGE`, `ADMIN_AGENT_REVOKED`, and `ADMIN_REQUEST_TOO_LARGE`. Error messages never include a submitted password, refresh token, phone or barcode.

## Audited mutations — TASK-011B

All mutation routes use the Admin bearer session, exact allowlisted Origin, `X-Admin-Request: 1`, HTTPS policy, request validation, and a single SQL transaction for the state change plus audit row. Managers are denied business/agent mutations by backend RBAC; they may unbind only cards selected by their authenticated business scope.

| Endpoint | Method | Role | Contract |
|---|---|---|---|
| `/admin/businesses` | POST | Superadmin | Create `{name, logo_url?, colors?, barcode_prefixes?, status?}`; status defaults to `active`; returns read view with counts |
| `/admin/businesses/{business_id}` | PATCH | Superadmin | Partial update of those same fields; `name`/`status` cannot be null |
| `/admin/agents` | POST | Superadmin | `{business_id}`; creates Agent using the existing `agk_` + SHA-256 key mechanism and returns `{agent, api_key}` once |
| `/admin/agents/{agent_id}/rotate-key` | POST | Superadmin | Atomically replaces the existing key hash and returns the new `{agent, api_key}` once |
| `/admin/agents/{agent_id}/revoke` | POST | Superadmin | Sets Agent status to `revoked`; repeat requests are idempotent |
| `/admin/agents/{agent_id}/full-resync` | POST | Superadmin | Returns `202 {command_id, status, execution: "deferred"}` and durably records a pending command |
| `/admin/cards/{card_id}/unbind` | POST | Superadmin or in-scope manager | Deletes only the `UserCard` relation; returns `{status: "unbound"}` or idempotent `{status: "already_unbound"}` |

Business status is restricted to the values used by the backend (`active`, `inactive`). `logo_url` is HTTPS-only and rejects embedded credentials and other schemes. Colors must be a bounded JSON object (maximum 8 KiB, bounded nesting/entry count); the complete business mutation body is capped at 16 KiB. `barcode_prefixes` accepts `null` or an empty list; no barcode-prefix rules are inferred.

The raw Agent key uses the existing `/agent/auth` key format and verification behavior. It exists in the Admin response only after the corresponding transaction commits. No key read endpoint exists; list/detail APIs return no raw key or hash. The SPA holds disclosure only in transient component state, offers copying only on a user click, and clears it when the disclosure dialog closes. It is never placed in URLs, browser storage, or query cache.

`agent_commands` has a PostgreSQL partial unique index allowing at most one `full_resync` command in `pending`/`running` state per Agent. Retries return the existing active command ID and do not add another audit event. No Agent command-polling/execution protocol exists yet; this API records a request and intentionally reports `execution: "deferred"`, never completion.

Card unbind locks the scoped Card and its `UserCard` row. Concurrent/repeated requests converge on one deletion; later requests report `already_unbound`. Card, User, barcode, balance, and Business data remain unchanged. No Admin arbitrary rebind is exposed.

`audit_log` now has nullable `admin_user_id` and `business_id` foreign keys; existing rows remain global legacy entries with both fields NULL. New Admin mutations set actor and tenant from authenticated database rows, and audit/state commit atomically with the mutation. Secret-looking fields, Agent key formats, JWT/refresh patterns, and URL query/fragment values are redacted. Business audit snapshots retain configured color keys but redact color values. Business managers receive only SQL-filtered rows for their own `business_id`; legacy NULL-scoped entries are invisible to managers, while superadmins retain global visibility.
