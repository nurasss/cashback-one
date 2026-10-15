# TASK-009 FIX-D — Stage 0 Final Toolkit Cleanup & Windows Runbook Report

## Balance Source Neutrality
- Removed all presumptions that loyalty balance must be stored in a register or single attribute.
- Replaced field description in `CardMapping.balance_source`:
  `Exact verified source or derivation rule for the current loyalty balance`
- Replaced report status in `STAGE0_DISCOVERY_REPORT.md`:
  `NOT VERIFIED: Requires identification and verification of the actual balance source.`
- The schema and discovery toolkit no longer make assumptions regarding whether balance is sourced from an accumulation register, an attribute, a document, or a calculated read-model.

## Blocked-State Neutrality
- Removed all presumptions that card blocking is represented by a deletion mark (`DeletionMark`) or a specific boolean flag.
- Replaced field description in `CardMapping.blocked_source`:
  `Exact verified source or deterministic rule used to derive Cloud is_blocked`
- Replaced report status in `STAGE0_DISCOVERY_REPORT.md`:
  `NOT VERIFIED: Requires identification of the actual source or rule for card availability/block status.`
- Supports arbitrary derivation mechanisms (deletion mark, status enum, boolean attribute, or complex business logic rule).

## Transaction Source Neutrality
- Removed all speculative assumptions that loyalty movements must come from documents or accumulation registers.
- Replaced field description in `TransactionMapping.source_object`:
  `Exact metadata source or deterministic read model containing loyalty movements`
- Replaced report status in `STAGE0_DISCOVERY_REPORT.md`:
  `NOT VERIFIED: Requires identification of the actual loyalty movement source.`

## Transaction-Type Neutrality
- Removed wording referring to "1C movement types".
- Replaced with neutral concept: `source movement semantics`.
- Replaced report status in `STAGE0_DISCOVERY_REPORT.md`:
  `NOT VERIFIED: Requires verification of source movement semantics and their deterministic mapping to the Cloud type string.`

## Optional Store / Receipt Semantics
- Removed all speculative presumptions regarding retail points and receipt entities.
- Store field description:
  `Optional verified source for the Cloud store field, or null when no reliable source exists`
- Store report status:
  `NOT VERIFIED: Requires verification whether a reliable source for the Cloud store field exists.`
- Receipt ref field description:
  `Optional safe source for Cloud receipt_ref, or null if no reliable source exists`
- Receipt report status:
  `NOT VERIFIED: Requires verification whether a safe source for Cloud receipt_ref exists without PII.`

## Updated-At Semantics
- Removed presumption that 1C objects have a direct modification timestamp attribute.
- Replaced field description in `CardMapping.updated_at_source`:
  `Verified source or deterministic versioning rule used to derive Card.updated_at semantics`
- Replaced report status in `STAGE0_DISCOVERY_REPORT.md`:
  `NOT VERIFIED: Requires identification of verified source or deterministic versioning rule for update semantics.`

## Candidate Heuristic Boundary
- Renamed candidate container and role to prevent implicit architectural bias:
  - `candidate_registers` → `candidate_balance_sources` (in `TargetedMetadataInventory`, with backward-compatible alias property).
  - Role: `balance_source_candidate` (instead of `balance_register`).
- Added explicit boundary notice to heuristics and inventory:
  `Category membership is only a search heuristic and is not evidence that the final mapping must use that category.`
- All heuristic candidate outputs explicitly state:
  `(heuristic candidates only; not mapping evidence; not verification)`.

## Windows Runbook
- Created comprehensive runbook: `docs/STAGE0_WINDOWS_RUNBOOK.md`.
- Conforms strictly to real CLI capabilities, security guidelines, and PowerShell syntax.
- Highlights:
  - Preflight environment verification.
  - Strictly read-only COM probe.
  - Mapping formulation and multi-level validation (`validate-mapping` with `--require-verified`).
  - Strict secret hygiene (`ONE_CONNECTION_STRING` never echoed or committed).

## CLI Contract Verification
- Verified real CLI commands via `--help`:
  - `poscenter-loyalty-agent stage0 check-environment [--output-dir OUTPUT_DIR]`
  - `poscenter-loyalty-agent stage0 probe-metadata [--output-dir OUTPUT_DIR] [--use-fake-provider]`
  - `poscenter-loyalty-agent stage0 validate-mapping mapping_file [--require-verified]`
- Confirmed absence of non-existent arguments/commands:
  - **No `--connection-string` CLI parameter:** connection strings are supplied securely via `$env:ONE_CONNECTION_STRING`.
  - **No `stage0 generate-mapping` CLI command:** mappings are constructed from empirical findings and validated via `validate-mapping`.

## Zero-Assumption Regression
- Implemented automated regression test `test_zero_speculative_semantic_phrases_in_stage0_and_reports` in `agent/tests/test_stage0.py`.
- Enforces zero occurrences of forbidden semantic phrases across all `agent/src/poscenter_loyalty_agent/stage0/*.py` sources and generated report artifacts:
  - `accumulation register or balance source`
  - `deletion mark or blocked flag`
  - `bonus movement document/register`
  - `1C movement types`
  - `retail point / store link`
  - `Register or attribute supplying`
  - `blocked / deletion mark`
  - `Store / retail point reference`

## Phase B Status
Execution on macOS (`darwin`) remains blocked by platform requirements (no `pywin32`, no `V83.COMConnector`):
```text
TASK-009 PHASE A = COMPLETE
TASK-009 PHASE B = BLOCKED_BY_REAL_ONE_ENVIRONMENT

REAL_WINDOWS_SERVICE = NOT VERIFIED
REAL_V83_COMCONNECTOR = NOT VERIFIED
REAL_ONE_CONNECTION = NOT VERIFIED
REAL_ONE_METADATA_DISCOVERY = NOT VERIFIED
REAL_ONE_MAPPING = NOT VERIFIED
```

## Agent Tests
Executed: `pytest -v agent/tests`
Result: **76 passed in 4.01s**

## Backend Regression
Executed: `pytest -v -m "not slow"` in `backend/`
Result: **176 passed, 29 skipped in 25.45s**

## PostgreSQL Regression
Executed: `POSTGRES_TEST_URL="postgresql+asyncpg://nuras@localhost:5432/poscenter_loyalty_test" pytest -v tests/test_postgres_*.py` in `backend/`
Result: **29 passed in 14.65s**

## Ruff
Executed:
- `agent/`: `ruff check src tests` → **All checks passed!**
- `backend/`: `ruff check app tests migrations` → **All checks passed!**

## Mypy
Executed:
- `agent/`: `mypy src tests` → **Success: no issues found in 35 source files**
- `backend/`: `mypy app migrations` → **Success: no issues found in 41 source files**

## Compileall
Executed:
- `agent/`: `python -m compileall src tests` → **Zero syntax errors**
- `backend/`: `python -m compileall app tests migrations` → **Zero syntax errors**

## Git Status
- Clean working directory with modified Stage 0 sources and new documentation.

## Branch
`main`

## HEAD
Initial HEAD: `f6a287338d96dc6e20aa9a146f3d6be99e8791f5`
