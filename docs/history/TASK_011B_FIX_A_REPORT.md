# TASK-011B-FIX-A Report — Audit Secret Disclosure & Business Colors Contract

## Executive Summary

Following an independent code review of TASK-011B, two blocking findings (P0 and P1) and one non-blocking README documentation inconsistency were identified and resolved in this narrow follow-up fix (`TASK-011B-FIX-A`):

1. **Fix 1 — P0 (Legacy Audit Snapshot Secret Disclosure):**
   Historical `AuditLog` rows containing sensitive connection strings (`DATABASE_URL`, `ONE_CONNECTION_STRING`) or arbitrary nested secrets (e.g. `password`, `token`, credentials) could previously be disclosed through `GET /admin/audit`. A fail-closed security boundary was established across both read (serialization) and write boundaries:
   - For all legacy and unknown events, `before_state` and `after_state` fail-closed to `None` (`null` in JSON). Historical audit rows are preserved intact in PostgreSQL/SQLite.
   - For known Admin mutation events (`business_created`, `business_updated`, `agent_created`, `agent_key_rotated`, `agent_revoked`, `agent_full_resync_requested`, `card_unbound`), an explicit projection allowlist extracts only safe fields (`id`, `name`, `status`, `logo_url`, `colors`, `barcode_prefixes`, `colors_changed`, `agent_id`, `business_id`, `command_id`, `card_id`, `user_id`, `rotated_at`, `key_rotated`, `unbound`).
   - Deep recursive credential/secret redactors (`_safe_audit_value`, `_is_sensitive_audit_key`, `_CONTAINS_CREDENTIALS`, `_SECRET_VALUE`) provide defense in depth, stripping raw API keys, key hashes, passwords, URIs with credentials, and connection string parameters.

2. **Fix 2 — P1 (Business Colors Contract & Customer Wallet Protection):**
   `BusinessBranding` schema in Customer Wallet expects string or null values for `primary`, `primary_color`, `accent`, and `accent_color`. In TASK-011B, `POST /admin/businesses` accepted arbitrary JSON types (e.g. `{"primary": 123, "accent": {"bad": "type"}}`), which caused `GET /me/cards` to crash with HTTP 500 when rendering customer cards.
   - Enforced strict validation in `_validate_colors()` for both `BusinessCreateRequest` (`POST /admin/businesses`) and `BusinessUpdateRequest` (`PATCH /admin/businesses/{id}`).
   - Non-string, non-null values for known branding color keys (`primary`, `primary_color`, `accent`, `accent_color`) are rejected immediately with HTTP 422 `VALIDATION_ERROR`.
   - Length bounding (max 128 characters per color entry) and payload bounding (max 64 entries, max 8 KiB JSON) were maintained.

3. **README Cleanup:**
   Updated `admin/README.md` to remove obsolete TASK-011A text stating that the Admin UI is read-only with no mutation screens, reflecting current full-stack mutation capabilities.

---

## Findings Fixed

| Finding ID | Severity | Area | Symptom / Risk | Resolution |
|------------|----------|------|----------------|------------|
| FINDING-1 | P0 | Audit Log API (`GET /admin/audit`) | Superadmin could view raw credentials from legacy `before_state`/`after_state` (e.g. `ONE_CONNECTION_STRING`, `DATABASE_URL`, nested passwords) | Fail-closed projection (`safe_audit_snapshot`): unknown/legacy events return `null` state; known events strictly allowlist safe fields and recursively redact secrets |
| FINDING-2 | P1 | Business Mutation (`POST /admin/businesses`, `PATCH /admin/businesses/{id}`) | Non-string colors (e.g. `{"primary": 123}`) were stored, breaking Customer Wallet `GET /me/cards` with HTTP 500 | `_validate_colors()` rejects non-string/non-null branding keys with HTTP 422 `VALIDATION_ERROR` |
| FINDING-3 | Non-blocking | Documentation (`admin/README.md`) | README claimed Admin UI is read-only without mutation screens | Clarified full support for operational monitoring and atomic administrative mutations |

---

## Fix 1 Implementation Details (P0)

### 1. Fail-Closed Action Projection Allowlist
In `backend/app/services/admin_mutations.py`:
- Defined `_ALLOWED_AUDIT_ACTION_FIELDS` strictly enumerating allowed attributes per action:
  - `business_created`: `{"id", "name", "status", "logo_url", "colors", "barcode_prefixes", "colors_changed"}`
  - `business_updated`: `{"id", "name", "status", "logo_url", "colors", "barcode_prefixes", "colors_changed"}`
  - `agent_created`: `{"agent_id", "business_id", "status"}`
  - `agent_key_rotated`: `{"agent_id", "business_id", "key_rotated", "rotated_at"}`
  - `agent_revoked`: `{"agent_id", "business_id", "status"}`
  - `agent_full_resync_requested`: `{"command_id", "agent_id", "business_id", "status"}`
  - `card_unbound`: `{"card_id", "business_id", "user_id", "unbound"}`

### 2. Dual Boundary Defense
- **Read Boundary (`backend/app/services/admin_queries.py:list_audit_logs`):**
  When mapping `AuditItem`:
  ```python
  before_state=safe_audit_snapshot(row.action, row.before_state),
  after_state=safe_audit_snapshot(row.action, row.after_state),
  ```
  If `row.action` is not in `_ALLOWED_AUDIT_ACTION_FIELDS` (historical/legacy rows, arbitrary actions), it fails closed immediately and returns `None` (`null` in API JSON).
- **Write Boundary (`backend/app/services/admin_mutations.py:_audit`):**
  When inserting new `AuditLog` rows, `safe_audit_snapshot(action, state)` is applied to both `before_state` and `after_state`. No raw keys, hashes, or secrets are ever persisted to the audit table.

### 3. Deep Recursive Secret Redactor
- Expanded sensitive key regex `_SENSITIVE_AUDIT_KEY`:
  Detects `password`, `passwd`, `pwd`, `token`, `secret`, `jwt`, `otp`, `wappi`, `key_hash`, `agent_key`, `api_key`, `phone`, `barcode` (excluding `barcode_prefixes`), `full_name`, `credential`, `database_url`, `connection_string`, `connection_password`, `authorization`, `cookie`, `signing_key`, `private_key`.
- Credential string detector `_CONTAINS_CREDENTIALS` & `_SECRET_VALUE`:
  Identifies and redacts connection strings (e.g. `Password=...`), URIs with embedded credentials (e.g. `postgres://user:pass@host/db`), and tokens (`agk_`, `rfr_`, `Bearer`, `eyJ...`).

---

## Fix 2 Implementation Details (P1)

### 1. Branding Colors Validation
In `backend/app/schemas/admin.py`:
- Target consumer: `BusinessBranding` schema in `backend/app/schemas/wallet.py` (`logo_url: str | None`, `primary_color: str | None`, `accent_color: str | None`) and `extract_branding()` in `backend/app/services/wallet_service.py` reading:
  - `primary_color` or `primary`
  - `accent_color` or `accent`
- Added validation in `_validate_colors()`:
  ```python
  _KNOWN_BRANDING_COLOR_KEYS = {"primary", "primary_color", "accent", "accent_color"}

  for key in _KNOWN_BRANDING_COLOR_KEYS:
      if key in value:
          color_val = value[key]
          if color_val is not None and not isinstance(color_val, str):
              raise ValueError(f"{key} must be a string or null")
          if isinstance(color_val, str) and len(color_val) > 128:
              raise ValueError(f"{key} is too long")
  ```
- Both `BusinessCreateRequest` (POST) and `BusinessUpdateRequest` (PATCH) validate colors through `_validate_colors`, guaranteeing that invalid payloads return HTTP 422 `VALIDATION_ERROR`.

---

## README Cleanup

Updated `admin/README.md`:
- Replaced outdated TASK-011A header and read-only description with an accurate overview of the Admin console's capabilities, including atomic mutations: creating/editing businesses, provisioning POS agents, rotating agent keys, revoking agents, requesting full resyncs, and unbinding customer cards.

---

## Security Boundaries & Invariants

1. **AuditLog Untrusted Storage Invariant:**
   The `AuditLog` table is never assumed to be trusted. Legacy rows containing historical secrets are completely sanitized at read time. Caller role (superadmin vs manager) does not bypass secret redaction.
2. **Manager Tenant Isolation:**
   Business managers cannot see legacy audit records (which have `business_id = NULL`). Global superadmin sees historical records with `before_state: null, after_state: null`.
3. **One-Time Key Disclosure:**
   Agent API keys are disclosed only in the mutation response of creation or rotation; they never enter audit logs or database tables (only SHA-256 `key_hash` is stored in `agents`).
4. **Customer Wallet Compatibility:**
   Admin business branding mutations are contractually verified to always produce payloads consumable by `BusinessBranding`, preventing 500 runtime errors in `/me/cards`.

---

## Test Evidence

### 1. Targeted Unit & Regression Tests (`backend/tests/test_admin_mutations.py`)

Executed with:
```bash
DATABASE_URL="sqlite+aiosqlite:///:memory:" APP_ENV=test /Users/nuras/Desktop/cashback-one/.venv/bin/pytest -v backend/tests/test_admin_mutations.py
```

Output:
```
============================= test session starts ==============================
platform darwin -- Python 3.14.7, pytest-9.1.1, pluggy-1.6.0 -- /Users/nuras/Desktop/cashback-one/.venv/bin/python3.14
rootdir: /Users/nuras/Desktop/cashback-one-task-011b/backend
configfile: pyproject.toml
plugins: asyncio-1.4.0, anyio-4.15.1
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 10 items

backend/tests/test_admin_mutations.py::test_audit_snapshot_removes_secret_fields_and_redacts_secret_values PASSED [ 10%]
backend/tests/test_admin_mutations.py::test_business_create_update_validation_and_audit_are_atomic PASSED [ 20%]
backend/tests/test_admin_mutations.py::test_manager_cannot_run_any_superadmin_mutation PASSED [ 30%]
backend/tests/test_admin_mutations.py::test_agent_key_one_time_rotation_revocation_and_audit PASSED [ 40%]
backend/tests/test_admin_mutations.py::test_full_resync_is_durable_idempotent_and_stays_pending PASSED [ 50%]
backend/tests/test_admin_mutations.py::test_manager_unbind_is_scoped_idempotent_and_does_not_delete_business_data PASSED [ 60%]
backend/tests/test_admin_mutations.py::test_legacy_audit_snapshot_secrets_are_never_disclosed_at_read_time PASSED [ 70%]
backend/tests/test_mutation_audit_events_never_record_raw_keys_hashes_or_passwords PASSED [ 80%]
backend/tests/test_business_colors_validation_rejects_non_string_types PASSED [ 90%]
backend/tests/test_business_colors_contract_with_customer_wallet_end_to_end PASSED [100%]

============================== 10 passed in 4.12s ==============================
```

### 2. Full Backend Pytest Suite

Executed with:
```bash
DATABASE_URL="sqlite+aiosqlite:///:memory:" APP_ENV=test /Users/nuras/Desktop/cashback-one/.venv/bin/pytest -v -m "not slow" backend/tests/
```
Result: **208 passed, 36 skipped in 25.69s** (exit code 0).

### 3. PostgreSQL Concurrency & Admin Security Tests

Executed against local PostgreSQL database `poscenter_loyalty_test`:
```bash
POSTGRES_TEST_URL="postgresql+asyncpg://nuras@localhost:5432/poscenter_loyalty_test" APP_ENV=test /Users/nuras/Desktop/cashback-one/.venv/bin/pytest -v backend/tests/test_postgres_*.py
```
Result: **36 passed in 23.03s** (exit code 0).

---

## Quality Gates

### Backend
| Check | Command | Result |
|-------|---------|--------|
| Pytest (Unit/Functional) | `pytest -v -m "not slow"` | **PASS** (208 passed, 36 skipped) |
| Pytest (PostgreSQL) | `POSTGRES_TEST_URL=... pytest -v tests/test_postgres_*.py` | **PASS** (36 passed) |
| Linter | `ruff check app tests migrations` | **PASS** (All checks passed!) |
| Type Checker | `mypy app migrations` | **PASS** (Success: no issues found in 56 source files) |
| Bytecode Compilation | `python -m compileall app tests migrations` | **PASS** (exit code 0) |

### Admin Frontend
| Check | Command | Result |
|-------|---------|--------|
| Unit / Integration Tests | `npm test` | **PASS** (6 test files, 44 tests passed) |
| Type Checker | `npm run typecheck` | **PASS** (`tsc --noEmit` clean) |
| Linter | `npm run lint` | **PASS** (`eslint .` clean) |
| Production Build | `npm run build` | **PASS** (built in 369ms) |
| Vulnerability Audit | `npm audit` | **PASS** (0 vulnerabilities) |

### Mobile
| Check | Command | Result |
|-------|---------|--------|
| Unit / Component Tests | `npm test` | **PASS** (5 suites, 81 tests passed) |
| Type Checker | `npm run typecheck` | **PASS** (`tsc --noEmit` clean) |
| Linter | `npm run lint` | **PASS** (`eslint .` clean) |
| Production Export | `npm run export` | **PASS** (Android and iOS bundles exported successfully) |

### Agent
| Check | Command | Result |
|-------|---------|--------|
| Unit / Contract Tests | `PYTHONPATH=src pytest -v` | **PASS** (76 tests passed) |
| Linter | `ruff check src tests` | **PASS** (All checks passed!) |
| Type Checker | `mypy src tests` | **PASS** (Success: no issues found in 35 source files) |
| Bytecode Compilation | `python -m compileall src tests` | **PASS** (exit code 0) |

---

## Git State & Verification

- **Branch:** `task-011b-fix-a`
- **Parent Commit:** `239b804108532a3faecaa9230abd39995c88c480`
- **Modified Files:**
  - `admin/README.md`
  - `backend/app/schemas/admin.py`
  - `backend/app/services/admin_mutations.py`
  - `backend/app/services/admin_queries.py`
  - `backend/tests/test_admin_mutations.py`
  - `docs/TASK_011B_FIX_A_REPORT.md`
