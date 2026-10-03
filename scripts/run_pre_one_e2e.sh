#!/usr/bin/env bash
# ==============================================================================
# POSCENTER Loyalty — Pre-ONE End-to-End Integration Suite Runner (TASK-013 FIX-A)
# ==============================================================================
# Executes hermetic end-to-end integration scenario verifying the full chain:
# TestLoyaltySource -> Real Agent Runtime -> Real HTTP Cloud API -> Real DB/Redis
#
# FIX-A safety:
# - Never prints full DB/Redis URLs, passwords, tokens or keys.
# - Prints only safe components (host/port/name, redis host/port/db).
# - Single Redis source of truth: REDIS_URL.
# - Canonical DB prefix: cashback_e2e_
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

echo "========================================================================"
echo " POSCENTER Loyalty — Pre-ONE End-to-End Integration Runner"
echo " Repo root: ${REPO_ROOT}"
echo "========================================================================"

# 1. Locate Python environment
if [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
    PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
    PYTEST_BIN="${REPO_ROOT}/.venv/bin/pytest"
elif [[ -x "/Users/nuras/Desktop/cashback-one/.venv/bin/python" ]]; then
    PYTHON_BIN="/Users/nuras/Desktop/cashback-one/.venv/bin/python"
    PYTEST_BIN="/Users/nuras/Desktop/cashback-one/.venv/bin/pytest"
elif command -v python3 &>/dev/null; then
    PYTHON_BIN="$(command -v python3)"
    PYTEST_BIN="$(command -v pytest || echo "${PYTHON_BIN} -m pytest")"
else
    echo "ERROR: Python 3 not found." >&2
    exit 1
fi

# 2. Canonical E2E targets (single source of truth).
#    DB default uses strict canonical prefix cashback_e2e_.
export POSTGRES_E2E_URL="${POSTGRES_E2E_URL:-${POSTGRES_TEST_URL:-postgresql+asyncpg://nuras@localhost:5432/cashback_e2e_local}}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379/14}"
export PYTHONPATH="${REPO_ROOT}:${REPO_ROOT}/backend:${REPO_ROOT}/agent/src:${PYTHONPATH:-}"

# 2a. Conflicting Redis declarations must fail fast (no DB14 vs DB15 ambiguity).
if [[ -n "${REDIS_E2E_URL:-}" && "${REDIS_E2E_URL}" != "${REDIS_URL}" ]]; then
    echo "REDIS SAFETY ABORT: Conflicting REDIS_URL and REDIS_E2E_URL. Use single REDIS_URL." >&2
    exit 1
fi

# 2b. Verify Redis connectivity (no credentials printed).
if command -v redis-cli &>/dev/null; then
    if ! redis-cli ping &>/dev/null; then
        echo "Redis not responding on default port, attempting daemon start..."
        if command -v redis-server &>/dev/null; then
            redis-server --daemonize yes || true
            sleep 1
        fi
    fi
fi

# 2c. Validate targets structurally and print SAFE components only.
#     Raw URLs, usernames and passwords are never emitted.
"${PYTHON_BIN}" - <<'PY'
import os, sys
sys.path.insert(0, os.environ.get("REPO_ROOT", "."))
# Repo root is cwd (runner cd'd there).
sys.path.insert(0, ".")
try:
    from e2e.harness import safe_db_info, safe_redis_info
except Exception as exc:
    print(f"TARGET VALIDATION FAILED: cannot import safety helpers: {exc}", file=sys.stderr)
    sys.exit(1)

db_url = os.environ.get("POSTGRES_E2E_URL", "")
redis_url = os.environ.get("REDIS_URL", "")
try:
    db = safe_db_info(db_url)
    print(f"E2E DB target: host={db['host']} port={db['port']} database={db['database']}")
except Exception as exc:
    print(f"DATABASE SAFETY ABORT: {exc}", file=sys.stderr)
    sys.exit(1)
try:
    rd = safe_redis_info(redis_url)
    print(f"E2E Redis target: host={rd['host']} port={rd['port']} db={rd['db']}")
except Exception as exc:
    print(f"REDIS SAFETY ABORT: {exc}", file=sys.stderr)
    sys.exit(1)
PY

echo "Running Pre-ONE E2E test suite..."
echo "------------------------------------------------------------------------"

${PYTEST_BIN} -v -s -o asyncio_mode=auto e2e/test_pre_one_flow.py e2e/test_resource_safety.py "$@"

EXIT_CODE=$?

echo "------------------------------------------------------------------------"
if [[ ${EXIT_CODE} -eq 0 ]]; then
    echo "SUCCESS: All Pre-ONE End-to-End integration scenarios passed."
else
    echo "FAILURE: Pre-ONE E2E tests failed with exit code ${EXIT_CODE}."
fi
echo "========================================================================"

exit ${EXIT_CODE}
