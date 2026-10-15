# TASK-011B-FIX-C Report: Eliminate User-Controlled Secrets from Admin Audit Snapshots

## Summary
In TASK-011B-FIX-C, we remediated the remaining P0 audit secret disclosure finding where active Agent API keys (or arbitrary user-controlled credentials like JWTs, connection strings, or passwords) could be exfiltrated via Business configuration mutations (`POST /admin/businesses`, `PATCH /admin/businesses/{id}`).

The solution completely eliminates user-controlled free-form text values (`name`, `logo_url`, `colors` dictionary keys/values, `barcode_prefixes` string array) from audit log persistence and serialization. Instead, audit snapshots store and project strictly safe **semantic change metadata** (`business_id`, finite domain `status`, allowlisted `configured_fields`, `changed_fields`, `colors_changed`, and safe boolean metadata `colors: {"configured": True}`).

Historical snapshots with trusted provenance from FIX-B are projected fail-closed: all free-form string values and arbitrary mapping keys are stripped at read time, converting to semantic category representations without disclosing historical secret values.

---

## Baseline
- **Starting Branch:** `task-011b-fix-b`
- **Starting HEAD:** `6bdc57f9a95bfff9a5c909078bf336cca10cce9e`
- **Previous Parent:** `20c2a7751156f9f5fd9e57f229c1e45dd7b6c4e4`
- **New Branch:** `task-011b-fix-c`

---

## Root Cause
In TASK-011B-FIX-B, provenance and nested schema validation were introduced, but the implementation operated under the assumption that "allowlisted string fields contain safe values":
- Free-form strings (`name`, `logo_url`, `colors` values, `barcode_prefixes`) were stored in `before_state` and `after_state`.
- In `PATCH /admin/businesses/{id}`, an attacker or operator could inject an active Agent API key `K` into `name` (`"Business " + K`), `logo_url` (`"https://cdn.example.test/" + K + ".svg"`), or `colors` (`{K: "#ffffff"}`).
- The raw key `K` was written to `AuditLog.after_state` in the database.
- A business manager calling `GET /admin/audit` received `K` in the audit history and could use `K` against `/agent/heartbeat`.

Blacklists or regex-based secret detection cannot reliably identify arbitrary high-entropy credentials or custom tokens. Therefore, storing arbitrary user request values in audit logs is inherently unsafe.

---

## Audit Threat Model
- **Threat Actor:** Tenant manager or auditor with access to `GET /admin/audit`.
- **Attack Vector:** Superadmin or privileged operator sets user-controlled configuration fields (name, logo URL, branding colors, barcode prefixes) that contain active API keys, session tokens, passwords, or connection strings.
- **Impact:** Privilege escalation; manager extracts Agent API keys or other sensitive credentials from audit logs and accesses agent endpoints (`/agent/heartbeat`, `/agent/sync/*`).
- **Mitigation:** Fail-closed semantic change logging. The audit system records *that* a field was configured or changed and *what category* of change occurred, but never stores or emits the raw user-controlled string values.

---

## Business Audit Semantic Schema
Audit snapshots for `business_created` and `business_updated` strictly enforce the following safe schema:

### Safe Finite Domains
- `_ALLOWED_BUSINESS_STATUSES`: `{"active", "inactive"}`
- `_ALLOWED_BUSINESS_FIELDS`: `{"barcode_prefixes", "colors", "logo_url", "name", "status"}`

### `business_created` Snapshot
```json
{
  "business_id": "00000000-0000-0000-0000-000000000001",
  "status": "active",
  "configured_fields": [
    "barcode_prefixes",
    "colors",
    "logo_url",
    "name",
    "status"
  ],
  "colors": {
    "configured": true
  }
}
```

### `business_updated` Snapshots
- **`before_state`:**
  ```json
  {
    "business_id": "00000000-0000-0000-0000-000000000001",
    "status": "active",
    "configured_fields": [
      "barcode_prefixes",
      "colors",
      "logo_url",
      "name",
      "status"
    ],
    "colors": {
      "configured": true
    }
  }
  ```
- **`after_state`:**
  ```json
  {
    "business_id": "00000000-0000-0000-0000-000000000001",
    "status": "inactive",
    "changed_fields": [
      "barcode_prefixes",
      "name",
      "status"
    ],
    "colors_changed": false,
    "colors": {
      "configured": true
    }
  }
  ```

---

## Write-Time Boundary
In `backend/app/services/admin_mutations.py`:
- `_business_state(business, changed_fields=..., colors_changed=...)` produces only the semantic dictionary.
- Neither `business.name`, `business.logo_url`, `business.barcode_prefixes`, nor any raw keys/values of `business.colors` are placed into the audit state.
- `_audit(db, actor, business_id, action, entity, before_state, after_state)` applies `safe_audit_snapshot` before adding the `AuditLog` row to the database session.
- Result: Raw database queries (`SELECT before_state, after_state FROM audit_logs;`) verify that no free-form text or active credentials exist in PostgreSQL.

---

## Read-Time Boundary
In `_project_action_snapshot(action, value)`:
- Keys `"name"`, `"logo_url"`, `"barcode_prefixes"` are never projected.
- If `"colors"` is present in `value`, `_clean_colors` strictly projects `{"configured": True}` (or boolean `configured` flag); all raw keys and values are discarded.
- `status` is projected only if it matches `_ALLOWED_BUSINESS_STATUSES`.
- `configured_fields` and `changed_fields` are filtered against `_ALLOWED_BUSINESS_FIELDS`.
- All other actions (`agent_created`, `agent_key_rotated`, `agent_revoked`, `agent_full_resync_requested`, `card_unbound`) project only server-generated UUIDs, finite enum statuses, timestamps, and booleans.

---

## Historical Snapshot Handling
When reading historical audit rows written prior to FIX-C:
- If a trusted-provenance row contains raw values (`{"name": "...", "logo_url": "...", "colors": {"primary": "..."}}`), `_project_action_snapshot` derives the semantic categories (`changed_fields` / `configured_fields`) and converts colors to `{"configured": True}`.
- Free-form string values (`fixture-secret-a`, `fixture-secret-b`, `fixture-secret-c`) are discarded at serialization time.
- Legacy rows lacking structural Admin provenance (`admin_user_id == NULL` or `business_id == NULL`) continue to fail closed to `null`.

---

## Active Agent Key Reproduction
We implemented an end-to-end attack simulation test (`test_agent_api_key_cannot_be_exfiltrated_via_business_config_into_audit` in `backend/tests/test_admin_mutations.py`):
1. Superadmin created a business and an agent, obtaining active key `K` (`agk_...`).
2. Verified that `K` successfully authenticated against `/agent/heartbeat` (returned 200 OK).
3. Superadmin executed `PATCH /admin/businesses/{id}` with:
   - `name`: `"Injected Name " + K`
   - `logo_url`: `"https://cdn.example.test/" + K + ".svg"`
   - `colors`: `{K: "#ffffff"}`
4. The Business record was updated in the domain table (`name` and `logo_url` preserved for business operations).

---

## Database Secret Assertion
Directly queried the database `AuditLog` row for the `business_updated` mutation:
- `assert K not in str(updated_audit.before_state)`: PASSED.
- `assert K not in str(updated_audit.after_state)`: PASSED.
- `assert K not in str(updated_audit.entity)`: PASSED.
- `assert K not in str(updated_audit.action)`: PASSED.
- `assert K not in str(updated_audit.actor)`: PASSED.
- `assert K not in str(updated_audit.__dict__)`: PASSED.

---

## Superadmin API Assertion
Queried `GET /admin/audit` with superadmin credentials:
- `assert K not in superadmin_audit_resp.text`: PASSED (0 occurrences of `K`).

---

## Manager API Assertion
Queried `GET /admin/audit` with credentials of the manager for that business:
- `assert K not in manager_audit_resp.text`: PASSED (0 occurrences of `K`).
- Verified manager receives semantic metadata:
  - `changed_fields`: `["colors", "logo_url", "name"]`
  - `colors`: `{"configured": True}`
  - `name`: Not present.
  - `logo_url`: Not present.

---

## Agent Audit Regression
Tested `test_agent_create_and_rotate_audit_contain_no_raw_key_or_hash`:
- `agent_created` audit state contains `agent_id`, `business_id`, `status`.
- `agent_key_rotated` audit state contains `agent_id`, `business_id`, `key_rotated: true`, `rotated_at`.
- Neither raw keys (`agk_...`) nor `key_hash` values are ever recorded in the database or serialized via `GET /admin/audit`.

---

## Original FIX-B Regression
All FIX-B security invariants remain verified:
- `test_known_action_alone_without_admin_provenance_fails_closed`: Rows with `admin_user_id == NULL` fail closed to `before_state: null, after_state: null`.
- `test_legacy_audit_snapshot_with_known_action_fails_closed_and_never_discloses_secrets`: Legacy rows with known action strings fail closed.
- `test_trusted_admin_event_strict_shape_drops_malformed_and_opaque_structures`: Malformed payloads (dictionary name, dictionary status, mixed-type barcode prefixes) are stripped cleanly.
- `test_manager_unbind_is_scoped_idempotent_and_does_not_delete_business_data`: Tenant scoping and isolation remain intact.

---

## Business Colors Regression
The Business Colors P1 validation contract remains intact:
- `test_business_colors_validation_rejects_non_string_types`: Rejects non-string values with 422.
- `test_business_colors_contract_with_customer_wallet_end_to_end`: Customer wallet queries (`GET /me/cards`) return valid branding colors properly formatted.

---

## Backend Tests
- Pytest suite: **216 passed, 36 skipped** (concurrency tests requiring PostgreSQL).
- Ruff check: **All checks passed!**
- Mypy: **Success: no issues found in 56 source files**.
- Compileall: **All files compiled cleanly**.

---

## PostgreSQL Tests
Executed with `POSTGRES_TEST_URL="postgresql+asyncpg://nuras@localhost:5432/poscenter_loyalty_test"`:
- **36 passed in 14.12s**:
  - `test_postgres_admin_normalized_login_and_role_business_constraints`
  - `test_postgres_admin_refresh_rotation_has_one_concurrent_winner`
  - `test_postgres_admin_tenant_queries_never_return_foreign_rows`
  - `test_postgres_concurrent_admin_agent_rotations_leave_one_key_and_audit_each`
  - `test_postgres_concurrent_resync_requests_return_one_durable_command`
  - `test_postgres_concurrent_card_unbind_is_idempotent_and_audited_once`
  - `test_postgres_business_mutation_and_audit_roll_back_together`
  - All agent sync, wallet concurrency, auth concurrency, and wappi concurrency tests.

---

## Admin Regression
- `npm ci`: passed.
- `npm test`: **6 passed (44 tests total)**.
- `npm run typecheck`: passed with 0 errors.
- `npm run lint`: passed with 0 warnings/errors.
- `npm run build`: built production client bundle successfully.
- `npm audit`: **found 0 vulnerabilities**.

---

## Mobile Regression
- `npm ci`: passed.
- `npm test`: passed.
- `npm run typecheck`: passed with 0 errors.
- `npm run lint`: passed with 0 warnings/errors.
- `npm run export`: built iOS (`entry-882634851d1ef1a2da7696b89f69be9e.hbc`) and Android (`entry-08a679c8b39ce62c94f1d7828850e010.hbc`) bundles successfully.

---

## Agent Regression
- `PYTHONPATH=src pytest -v`: **76 passed in 2.80s**.
- `ruff check src tests`: **All checks passed!**
- `mypy src tests`: **Success: no issues found in 35 source files**.
- `python -m compileall src tests`: **All files compiled cleanly**.

---

## Files Changed
- `backend/app/services/admin_mutations.py`
  - Replaced free-form colors and text projection with finite domain constants (`_ALLOWED_BUSINESS_STATUSES`, `_ALLOWED_AGENT_STATUSES`, `_ALLOWED_COMMAND_STATUSES`, `_ALLOWED_BUSINESS_FIELDS`).
  - Redesigned `_clean_colors` to return only safe boolean metadata `{"configured": bool}`.
  - Updated `_project_action_snapshot` to drop all free-form text (`name`, `logo_url`, `barcode_prefixes`, raw colors dicts) and project semantic metadata only.
  - Redesigned `_business_state` to write semantic change metadata without raw user input.
- `backend/tests/test_admin_mutations.py`
  - Updated existing audit tests to assert semantic schema and lack of free-form values.
  - Added `test_agent_api_key_cannot_be_exfiltrated_via_business_config_into_audit`.
  - Added `test_historical_trusted_business_snapshot_drops_arbitrary_free_form_values`.
  - Added `test_real_business_updated_event_retains_useful_semantic_audit_metadata`.
  - Added `test_agent_create_and_rotate_audit_contain_no_raw_key_or_hash`.
- `docs/TASK_011B_FIX_C_REPORT.md` (this report)

---

## Git Commit & Status
- **Branch:** `task-011b-fix-c`
- **Commit Message:** `fix(admin): remove free-form values from audit snapshots`
