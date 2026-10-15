# TASK-011B-FIX-B Report — Fail-Closed Audit Snapshot Provenance & Strict Safe Projection

## Summary

This report documents the resolution of the remaining P0 finding identified during independent code review of TASK-011B-FIX-A. Previously, the audit sanitizer relied primarily on the `action` string matching an allowlist. A legacy `AuditLog` row with `admin_user_id = NULL` and a known action name (such as `"business_created"`) could disclose arbitrary nested JSON fields and sensitive values.

TASK-011B-FIX-B establishes a complete fail-closed security boundary:
1. **Structural Provenance Verification:** Audit snapshots are permitted only for events originating from the verified new Admin audit pipeline (`admin_user_id != NULL` and `business_id != NULL`). Legacy records lacking this provenance fail closed to `before_state = null` and `after_state = null`.
2. **Strict Per-Action Safe Projection:** Even with valid Admin provenance, arbitrary dictionaries and invalid scalar types are never passed through. Exact shape projectors validate allowed scalar types (strings, bounded lists) and clean branding/metadata color dictionaries, dropping any unknown or malformed nested data.

---

## Baseline

- **Base Branch:** `task-011b-fix-a`
- **Base Commit:** `20c2a7751156f9f5fd9e57f229c1e45dd7b6c4e4`
- **Parent Commit:** `239b804108532a3faecaa9230abd39995c88c480`
- **Working Tree:** Clean working tree verified prior to branching.
- **New Branch:** `task-011b-fix-b`

---

## Root Cause

In TASK-011B-FIX-A, `safe_audit_snapshot(action, value)` decided whether to project a snapshot based solely on `action in _ALLOWED_AUDIT_ACTION_FIELDS`. If an unmigrated or synthetic legacy `AuditLog` row in the database had:
```json
{
  "admin_user_id": null,
  "business_id": null,
  "action": "business_created",
  "before_state": {
    "colors": {
      "nested": {
        "opaque": "fixture-nested-secret"
      }
    },
    "name": {
      "label": "fixture-token-secret"
    }
  }
}
```
The sanitizer treated `"business_created"` as an allowed action. Because `"colors"` and `"name"` matched the action's key allowlist and the nested keys (`"opaque"`, `"label"`) did not match keyword blacklists, the arbitrary nested dictionary was returned to superadmin callers via `GET /admin/audit`.

---

## Structural Provenance Rule

Under TASK-011B-FIX-B:
`known action != trusted structured snapshot`

An audit snapshot is projected ONLY when confirmed structural markers of the new Admin audit pipeline exist on the database row:
1. `admin_user_id is not None`: In TASK-011B, all administrative mutations are performed by authenticated administrators, and `_audit()` always populates `admin_user_id = actor.id`. Historical legacy rows before TASK-011B consistently have `admin_user_id = NULL`.
2. `business_id is not None`: All seven supported Admin mutation actions (`business_created`, `business_updated`, `agent_created`, `agent_key_rotated`, `agent_revoked`, `agent_full_resync_requested`, `card_unbound`) are tenant-scoped. The mutation pipeline always assigns `business_id`.

If either `admin_user_id is None` or `business_id is None`, the snapshot fails closed immediately to `None` (`null` in JSON response).

---

## Legacy Known-Action Handling

- Historical rows are preserved in PostgreSQL / SQLite; no historical data is deleted.
- Superadmins querying `GET /admin/audit` can inspect the event metadata (`id`, `actor`, `action`, `entity`, `created_at`), but `before_state` and `after_state` are serialized as `null`.
- Business managers remain strictly isolated: legacy rows without `business_id` are invisible to managers due to the SQL tenant predicate `AuditLog.business_id == scope.business_id`.

---

## Strict Per-Action Projection

To prevent arbitrary nested payloads from passing through even on valid Admin events, projection logic validates exact safe types for each action:
- Scalars (`name`, `status`): Must be `str` (trimmed, max 255/32 chars). Dictionaries (e.g. `{"label": ...}`) or numbers are rejected and omitted.
- Identifiers (`id`, `agent_id`, `business_id`, `command_id`, `card_id`, `user_id`): Must be valid UUIDs or bounded strings.
- URLs (`logo_url`): Must be strings up to 1024 chars, sanitized via `_redact_url_query` and credential filters.
- Prefixes (`barcode_prefixes`): Must be a list of non-empty strings up to 32 chars each (max 64 entries). Non-string list items cause the field to be dropped.
- Colors (`colors`): Only two safe shapes are allowed:
  1. Administrative metadata shape: `{"configured": bool, "keys": list[str]}` (with clean strings).
  2. Branding colors shape: Keys restricted to `{"primary", "primary_color", "accent", "accent_color"}` with values `str | None`. Any unknown keys (e.g. `"nested"`, `"opaque"`) are dropped.
- Boolean flags (`key_rotated`, `colors_changed`, `unbound`): Must be `bool`.

---

## Business Snapshot Schema

For `business_created` and `business_updated`:
- `id` / `business_id`: UUID string
- `name`: string (1-255 chars)
- `status`: string (1-32 chars)
- `logo_url`: string | null (sanitized)
- `colors`: metadata dict or branding colors dict (`str | None` values)
- `barcode_prefixes`: list[str] | null
- `colors_changed`: bool (optional)

---

## Agent Snapshot Schema

For `agent_created`, `agent_key_rotated`, and `agent_revoked`:
- `agent_id`: UUID string
- `business_id`: UUID string
- `status`: string (for `created` and `revoked`)
- `key_rotated`: bool (for `rotated`)
- `rotated_at`: ISO timestamp string (for `rotated`)

Never allowed: `api_key`, `raw_key`, `key_hash`, `secret`, `token`.

---

## Resync Snapshot Schema

For `agent_full_resync_requested`:
- `command_id`: UUID string
- `agent_id`: UUID string
- `business_id`: UUID string
- `status`: string (optional)

---

## Card Unbind Snapshot Schema

For `card_unbound`:
- `card_id`: UUID string
- `business_id`: UUID string
- `user_id`: UUID string
- `unbound`: bool (optional)

---

## Read Boundary

In `backend/app/services/admin_queries.py:list_audit_logs`:
```python
before_state=safe_audit_snapshot(
    row.action,
    row.before_state,
    admin_user_id=row.admin_user_id,
    business_id=row.business_id,
),
after_state=safe_audit_snapshot(
    row.action,
    row.after_state,
    admin_user_id=row.admin_user_id,
    business_id=row.business_id,
),
```
Snapshots are evaluated directly from the row's structural properties prior to API response serialization.

---

## Write Boundary

In `backend/app/services/admin_mutations.py:_audit`:
```python
db.add(
    AuditLog(
        actor=actor.login,
        admin_user_id=actor.id,
        business_id=business_id,
        action=action,
        entity=entity,
        before_state=safe_audit_snapshot(
            action,
            before_state,
            admin_user_id=actor.id,
            business_id=business_id,
        ),
        after_state=safe_audit_snapshot(
            action,
            after_state,
            admin_user_id=actor.id,
            business_id=business_id,
        ),
    )
)
```
The write boundary enforces strict shape validation before persisting audit entries.

---

## Legacy Regression Test

Implemented in `backend/tests/test_admin_mutations.py::test_legacy_audit_snapshot_with_known_action_fails_closed_and_never_discloses_secrets`:
- Created legacy row: `admin_user_id = None`, `business_id = None`, `action = "business_created"`, `before_state = {"colors": {"nested": {"opaque": "fixture-nested-secret"}}, "name": {"label": "fixture-token-secret"}}`.
- Superadmin calls `GET /admin/audit`.
- Confirmed status 200, response body contains neither `fixture-nested-secret` nor `fixture-token-secret`, and `before_state` / `after_state` are serialized as `null`.

---

## Trusted Event Regression Test

Implemented in `backend/tests/test_admin_mutations.py::test_trusted_new_admin_event_retains_safe_structured_snapshot`:
- Superadmin creates a Business via `POST /admin/businesses` with valid attributes (`name`, `logo_url`, `colors`, `barcode_prefixes`).
- Superadmin calls `GET /admin/audit`.
- Confirmed status 200, the `business_created` event has non-null `admin_user_id`, and `after_state` correctly contains `name`, `status`, and `barcode_prefixes`.

---

## Malformed Shape Regression Tests

1. `test_known_action_alone_without_admin_provenance_fails_closed`:
   Verified that valid payloads for `business_created`, `agent_created`, and `card_unbound` fail closed to `None` if `admin_user_id` or `business_id` is missing.
2. `test_trusted_admin_event_strict_shape_drops_malformed_and_opaque_structures`:
   Verified that when an event has valid Admin provenance:
   - `"name": {"label": "fixture-secret"}` is dropped.
   - `"status": {"secret": "fixture-secret"}` is dropped.
   - `"barcode_prefixes": ["123", {"secret": "fixture-secret"}]` is dropped.
   - `"colors": {"primary": "#123456", "nested": {"secret": "fixture-secret"}, "opaque": "real-secret-value"}` retains ONLY `"primary"`, dropping `"nested"` and `"opaque"`.
   - Neither `"fixture-secret"` nor `"real-secret-value"` appears in the projected output.

---

## Manager Isolation

- `backend/tests/test_admin_mutations.py::test_legacy_audit_snapshot_secrets_are_never_disclosed_at_read_time`:
  Verified that business managers only see their own business audit entries (`AuditLog.business_id == scope.business_id`) and cannot view legacy records with `business_id = NULL`.
- Superadmins see legacy event metadata, but unsafe snapshots are redacted to `null`.

---

## Original P1 Regression

The Business Colors Contract established in TASK-011B-FIX-A remains untouched and fully operational:
- `test_business_colors_validation_rejects_non_string_types` PASSED (422 on `primary: 123`, `accent: {"bad": "type"}`, `primary_color: []`, `accent_color: False`).
- `test_business_colors_contract_with_customer_wallet_end_to_end` PASSED (200 on `GET /me/cards`, valid `BusinessBranding` serialization).

---

## Backend Tests

Command:
```bash
DATABASE_URL="sqlite+aiosqlite:///:memory:" APP_ENV=test /Users/nuras/Desktop/cashback-one/.venv/bin/pytest -v -m "not slow" backend/tests/
```
Result: **212 passed, 36 skipped in 20.98s** (exit code 0).

Linters & Quality:
- `ruff check app tests migrations`: **All checks passed!**
- `mypy app migrations`: **Success: no issues found in 56 source files**
- `python -m compileall app tests migrations`: **Clean compilation**

---

## PostgreSQL Tests

Command:
```bash
POSTGRES_TEST_URL="postgresql+asyncpg://nuras@localhost:5432/poscenter_loyalty_test" APP_ENV=test /Users/nuras/Desktop/cashback-one/.venv/bin/pytest -v backend/tests/test_postgres_*.py
```
Result: **36 passed in 12.70s** (exit code 0).

---

## Admin Regression

Commands in `admin`:
- `npm test`: **6 test files passed, 44 tests passed in 8.14s**
- `npm run typecheck`: **Clean** (`tsc --noEmit`)
- `npm run lint`: **Clean** (`eslint .`)
- `npm run build`: **Built in 294ms**
- `npm audit`: **found 0 vulnerabilities**

---

## Mobile Regression

Commands in `mobile`:
- `npm test`: **5 suites passed, 81 tests passed**
- `npm run typecheck`: **Clean** (`tsc --noEmit`)
- `npm run lint`: **Clean** (`eslint .`)
- `npm run export`: **Exported iOS & Android bundles**

---

## Agent Regression

Commands in `agent`:
- `PYTHONPATH=src pytest -v`: **76 passed in 2.90s**
- `ruff check src tests`: **All checks passed!**
- `mypy src tests`: **Success: no issues found in 35 source files**
- `python -m compileall src tests`: **Clean compilation**

---

## Files Changed

- `backend/app/services/admin_mutations.py`
- `backend/app/services/admin_queries.py`
- `backend/tests/test_admin_mutations.py`
- `docs/TASK_011B_FIX_B_REPORT.md`

---

## Branch & HEAD

- **Branch:** `task-011b-fix-b`
- **Parent:** `20c2a7751156f9f5fd9e57f229c1e45dd7b6c4e4` (TASK-011B-FIX-A)
- **Commit:** `fix(admin): fail closed on legacy audit snapshots`

---

## Git Status

Clean working tree.
