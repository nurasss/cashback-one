# TASK-009 FIX-E — CWD-Independent Tests, Service Boundary & Structural Neutrality Report

## CWD-Independent Agent Tests
- Fixed working-directory coupling in `agent/tests/test_stage0.py`.
- Replaced hardcoded relative paths (`Path("agent/...")`) with paths anchored to `__file__`:
  ```python
  TESTS_DIR = Path(__file__).resolve().parent
  AGENT_DIR = TESTS_DIR.parent
  REPO_ROOT = AGENT_DIR.parent

  EXAMPLE_MAPPING = AGENT_DIR / "stage0_mapping.example.json"
  STAGE0_SRC_DIR = AGENT_DIR / "src" / "poscenter_loyalty_agent" / "stage0"
  RUNBOOK_PATH = REPO_ROOT / "docs" / "STAGE0_WINDOWS_RUNBOOK.md"
  ```
- All mapping example reads and source directory scans in tests now resolve deterministically regardless of execution working directory.

## Root Test Execution
- Executed from repository root:
  ```bash
  PYTHONPATH=agent/src pytest -v agent/tests
  ```
- Result: **76 passed in 3.20s**

## Agent Directory Test Execution
- Executed from `agent/`:
  ```bash
  cd agent
  PYTHONPATH=src pytest -v
  ```
- Result: **76 passed in 3.57s** (matching root execution exactly, 0 failures)

## Windows Service Verification Boundary
- Corrected the expected verification status in `docs/STAGE0_WINDOWS_RUNBOOK.md`:
  `REAL_WINDOWS_SERVICE` remains `NOT VERIFIED` during Stage 0 preflight checks and metadata probing on Windows.
- Added explicit boundary documentation in the runbook:
  `Running Stage 0 on Windows verifies only platform/COM/connectivity conditions. It does NOT verify Windows Service installation, SCM registration, start/stop behavior, recovery behavior, or service-account execution.`
- `REAL_WINDOWS_SERVICE` is preserved as `NOT VERIFIED` until an independent Windows Service lifecycle verification suite is conducted.

## Relationship Mapping Neutrality
- Removed structural assumptions regarding dimensions and requisites in `TransactionMapping.card_relationship`:
  - Previous: `Dimension or requisite linking movement to card`
  - Updated: `Verified source or deterministic relationship used to associate a movement with the loyalty card`
- Docstring of `TransactionMapping` updated to:
  `Verified mapping for loyalty transaction/movement data.`

## Transaction Amount Neutrality
- Removed assumption that transaction amount is a direct field:
  - Previous: `Field storing transaction bonus amount`
  - Updated: `Verified source or deterministic derivation rule for the Cloud transaction amount`

## Occurred-At Neutrality
- Removed assumption that movement timestamp is a direct field:
  - Previous: `Movement timestamp field`
  - Updated: `Verified source or deterministic rule used to derive the Cloud occurred_at timestamp`

## Balance-After Neutrality
- Removed assumption that balance after movement is a direct field:
  - Previous: `Field storing balance after movement, or null`
  - Updated: `Optional verified source or deterministic derivation rule for Cloud balance_after, or null when unavailable`

## Heuristic Wording
- Neutralized heuristic confidence reason in `CandidateDiscoveryHeuristic` (`metadata_probe.py`):
  - Previous: `Source matches sales / transaction / bonus movement keywords`
  - Updated: `Source matches configured transaction/movement candidate keywords; heuristic only, not mapping evidence.`

## Windows Runbook
- Updated `docs/STAGE0_WINDOWS_RUNBOOK.md` to reflect the strict `REAL_WINDOWS_SERVICE = NOT VERIFIED` boundary and clarified lifecycle separation.
- Preserved existing CLI contract (`check-environment`, `probe-metadata`, `validate-mapping`). No `--connection-string` or `generate-mapping` additions.

## Zero-Assumption Regression
- Expanded `test_zero_speculative_semantic_phrases_in_stage0_and_reports` in `agent/tests/test_stage0.py` with additional forbidden phrases:
  - `Dimension or requisite linking`
  - `Field storing transaction bonus amount`
  - `Movement timestamp field`
  - `Field storing balance after movement`
  - `REAL_WINDOWS_SERVICE:        VERIFIED (or Windows host confirmed)`
  - `REAL_WINDOWS_SERVICE: VERIFIED (or Windows host confirmed)`
- The test scans all `agent/src/poscenter_loyalty_agent/stage0/*.py` sources, synthetic generated reports, and `docs/STAGE0_WINDOWS_RUNBOOK.md`.

## Phase B Status
```text
TASK-009 PHASE A = COMPLETE
TASK-009 PHASE B = BLOCKED_BY_REAL_ONE_ENVIRONMENT

REAL_WINDOWS_SERVICE = NOT VERIFIED
REAL_V83_COMCONNECTOR = NOT VERIFIED
REAL_ONE_CONNECTION = NOT VERIFIED
REAL_ONE_METADATA_DISCOVERY = NOT VERIFIED
REAL_ONE_MAPPING = NOT VERIFIED

STATUS = READY_FOR_REAL_ONE_DISCOVERY
```

## Backend Regression
- Executed from `backend/`: `pytest -v -m "not slow"`
- Result: **176 passed, 29 skipped in 20.84s**

## PostgreSQL Regression
- Executed from `backend/`: `POSTGRES_TEST_URL="postgresql+asyncpg://nuras@localhost:5432/poscenter_loyalty_test" pytest -v tests/test_postgres_*.py`
- Result: **29 passed in 11.99s**

## Ruff
- `agent/`: `ruff check src tests` → **All checks passed!**
- `backend/`: `ruff check app tests migrations` → **All checks passed!**

## Mypy
- `agent/`: `mypy src tests` → **Success: no issues found in 35 source files**
- `backend/`: `mypy app migrations` → **Success: no issues found in 41 source files**

## Compileall
- `agent/`: `python -m compileall src tests` → **Zero syntax errors**
- `backend/`: `python -m compileall app tests migrations` → **Zero syntax errors**

## Git Status
- Working tree clean after staging and commit.

## Branch
`main`

## HEAD
Initial HEAD: `d1dc3d375e7a82c216601bf5ef9eba3345840188`
