# POSCENTER Loyalty Admin

Administrative web console built with Vite, React 19, TypeScript strict, React Router and TanStack Query. It communicates with the Cloud Backend Admin API; it does not connect to POSCENTER ONE directly. The console supports both operational monitoring and atomic administrative mutations: creating and editing businesses, provisioning POS agents, rotating agent keys, revoking agents, requesting full resyncs, and unbinding customer cards.

## Requirements and setup

- Node.js 20.19+ (Node 22 LTS recommended), npm.
- Python 3.11+, PostgreSQL and Redis for the backend.
- HTTPS browser origin and backend URL in production.

```bash
cd admin
npm ci
cp .env.example .env
# Set VITE_API_BASE_URL to the reachable backend origin.
npm run dev
```

Vite reads `VITE_API_BASE_URL` at build/dev-server start; restart after changing it. Vite-prefixed settings are visible to the browser and must not contain credentials. There is no default API origin.

Backend origins, the independent admin signing key and the explicit local-HTTP development switch are configured in the root `.env`. `ADMIN_ALLOWED_ORIGINS` is a JSON list of exact browser origins, e.g. `["https://admin.example.com"]`; wildcard origins are rejected. Set a separately generated `ADMIN_JWT_SIGNING_KEY` with at least 32 characters. Do not reuse the customer JWT key. Set `ADMIN_ALLOW_INSECURE_HTTP=1` only in `APP_ENV=development` when local testing actually needs HTTP. Production rejects HTTP origins and requests, regardless of that switch. For normal development, use HTTPS where available; the Vite app likewise requires HTTPS unless `import.meta.env.DEV` and `VITE_ALLOW_INSECURE_HTTP=1` are both true.

For local development, bind the backend to `0.0.0.0` when using another device and explicitly allow the Vite origin in `ADMIN_ALLOWED_ORIGINS`. A browser on another computer/device also needs the backend's reachable LAN URL in `VITE_API_BASE_URL`, with the explicit development HTTP settings above if the local test environment does not use TLS. Never set the insecure flag in production.

The Python dependencies are in `backend/requirements.txt`. Install optional backend quality tools with `cd backend && pip install -e '.[dev]'`. Apply schema changes using the normal deployment migration process before starting the updated backend.

## Safe initial administrator provisioning

No default account, password or backdoor route is created. After configuring the normal database and security environment, run locally on a trusted administrative host:

```bash
cd backend
python -m app.cli.create_admin
```

The command interactively requests a normalized login, asks for the password twice via a hidden terminal prompt, then asks for a role; for a business manager it also validates an existing business UUID. Passwords cannot be passed as command arguments and are stored only as Argon2id hashes. The one-time local process is not exposed over HTTP.

## Development, build and checks

```bash
npm run dev
npm test
npm run typecheck
npm run lint
npm run build
npm audit
```

The SPA has no server rendering. `npm run build` runs TypeScript then Vite. Audit findings must be reviewed and resolved with versions compatible with the pinned Expo/native dependencies in the monorepo; do not use `npm audit fix --force` blindly.

## Authentication and role boundaries

- Login refreshes through `/admin/auth/refresh`, then loads `/admin/me` before protected UI renders. Transient bootstrap/network errors show a retryable state instead of flashing Login.
- Access JWTs live only in a JavaScript-memory session object. The refresh token is never returned in JSON or read by JavaScript; FastAPI places it in an HttpOnly, SameSite=Lax cookie scoped to `/admin`. The cookie is Secure except for explicitly enabled local/LAN development HTTP.
- Every `/admin/*` request requires an exact allowlisted `Origin` and the `X-Admin-Request: 1` custom header. CORS credentials are enabled only for configured exact origins. TLS termination must pass the trusted external scheme to the ASGI server; see deployment settings for the trusted reverse-proxy boundary.
- Admin JWTs use the separate issuer, audience, `typ=admin_access` and signing secret. `/me/*` customer tokens do not satisfy the Admin dependency; Admin tokens do not satisfy customer authentication.
- Managers derive scope from their authenticated AdminUser. Manager queries add a `business_id = authenticated_admin.business_id` predicate in SQL. A manager cannot enumerate businesses or mutate businesses/agents. The audit view includes only structurally scoped rows for the manager's own business; legacy rows without a business key remain superadmin-only.
- Search submissions put phone/barcode criteria in POST bodies, never URLs. Card barcode comparisons preserve their exact 13-digit string, including leading zeroes. Phone lookup uses the existing backend `normalize_phone` function.
- Tables use bounded pages (1–100 rows) and deterministic timestamp/ID ordering. Agent health uses the server's configured stale threshold; the dashboard says “unblocked cards” and counts only `is_blocked = false`.
- Legacy `AuditLog` rows still have no business key and remain superadmin-only; Admin-created events are structurally tenant-scoped and safely display sanitized before/after state.

## Deployment response headers

Configure these at the TLS reverse proxy/static hosting layer (the SPA is a static build). Example policy; replace the API host with the deployment's actual origin:

```nginx
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' https:; connect-src 'self' https://api.example.com; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "no-referrer" always;
add_header X-Frame-Options "DENY" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

Only enable HSTS after all intended subdomains are HTTPS. A TLS reverse proxy must be on the backend's trusted proxy list so the application sees the real HTTPS scheme. Never configure credentialed CORS with `*`.

## Known limits and future work

- “Active card” has no confirmed business definition in the existing schema. Dashboard labels the measurable field `is_blocked = false` as “unblocked”, not “active”.
- Legacy `AuditLog` entries without `business_id` remain visible only to superadmins. Newly written Admin events carry structural tenant/admin foreign keys and sanitized before/after state.
- A full-resync request is persisted as pending, but Agent polling/execution remains deferred because no compatible command protocol exists yet.
- Business deletion, arbitrary Admin rebind, customer deletion, billing, activation flows, and full-name card search are not exposed. Agent API keys are disclosed only in the successful create/rotate response.
- Local/unit tests may use fixture records; production code always reads the real backend and has no fixture fallback.
- Existing backend `SMS_PROVIDER_MODE` is not changed by this Admin task.
