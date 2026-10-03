#!/usr/bin/env bash
# ==============================================================================
# POSCENTER Loyalty — Pre-ONE End-to-End Integration Suite Runner (TASK-013 FIX-B)
# ==============================================================================
# Executes hermetic end-to-end integration scenario verifying the full chain:
# TestLoyaltySource -> Real Agent Runtime -> Real HTTP Cloud API -> Real DB/Redis
#
# FIX-B safety:
# - Canonical preflight BEFORE pytest via same Python code (e2e.preflight).
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

# 1. Locate Python environment (no hardcoded developer paths).
if [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
    PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
    PYTEST_BIN="${REPO_ROOT}/.venv/bin/pytest"
elif command -v python3 &>/dev/null; then
    PYTHON_BIN="$(command -v python3)"
    PYTEST_BIN="$(command -v pytest || echo "${PYTHON_BIN} -m pytest")"
else
    echo "ERROR: Python 3 not found." >&2
    exit 1
fi

# 2. Canonical E2E targets (single source of truth).
#    DB default uses strict canonical prefix cashback_e2e_.
export POSTGRES_E2E_URL="${POSTGRES_E2E_URL:-${POSTGRES_TEST_URL:-postgresql+asyncpg://localhost:5432/cashback_e2e_local}}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379/14}"
export PYTHONPATH="${REPO_ROOT}:${REPO_ROOT}/backend:${REPO_ROOT}/agent/src:${PYTHONPATH:-}"

# 2a. Conflicting Redis declarations must fail fast (no DB14 vs DB15 ambiguity).
#     Safe message only (no URLs).
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

# 2c. Canonical preflight BEFORE pytest (same Python code, safe output only).
#     Reads URLs from environment (never CLI args). On failure pytest never starts.
echo "Running E2E preflight..."
if ! "${PYTHON_BIN}" -m e2e.preflight; then
    echo "E2E preflight refused unsafe target. pytest not started." >&2
    exit 1
fi

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
