# Admin API — TASK-011A

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
| `/admin/audit` | GET | `limit`, `offset` | Superadmin only; tenant-unscoped JSON states are omitted |

All list rows sort by a stable timestamp and ID tie-breaker. `Page<T>` is `{items, limit, offset, has_more}`; clients fetch another bounded page only when `has_more` is true.

Dashboard period timestamps must include a timezone, `from <= to`, and the range may not exceed `ADMIN_MAX_STATS_PERIOD_DAYS`. Values are compared in UTC. Customer count means distinct active profiles linked to a card in that business. “Unblocked cards” is exactly `is_blocked = false`. Agent health is calculated by the backend: `disabled`, `error`, `never_connected`, `stale`, or `online`; stale seconds come from `ADMIN_AGENT_STALE_SECONDS` (default 900). No API key hash is returned. Sensitive search values arrive in POST JSON and are not written to request/application logs.

`business_manager` scope always comes from the authenticated AdminUser row. A foreign tenant selector and foreign IDs return a uniform `404 ADMIN_RESOURCE_NOT_FOUND`; global businesses and unscopable AuditLog return `403 ADMIN_FORBIDDEN` without querying other-tenant payload rows.

## Error envelope

Errors use the existing `{ "error": { "code": "…", "message": "…" } }` contract. Admin additions are `INVALID_CREDENTIALS`, `ADMIN_UNAUTHENTICATED`, `ADMIN_FORBIDDEN`, `ADMIN_RESOURCE_NOT_FOUND`, `ADMIN_RATE_LIMITED`, `ADMIN_ORIGIN_FORBIDDEN`, `ADMIN_CSRF_BLOCKED`, `ADMIN_HTTPS_REQUIRED`, `ADMIN_INVALID_PERIOD`, and `ADMIN_PERIOD_TOO_LARGE`. Error messages never include a submitted password, refresh token, phone or barcode.
