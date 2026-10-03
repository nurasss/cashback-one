#!/usr/bin/env bash
# ==============================================================================
# POSCENTER Loyalty — Pre-ONE End-to-End Integration Suite Runner (TASK-013)
# ==============================================================================
# Executes hermetic end-to-end integration scenario verifying the full chain:
# TestLoyaltySource -> Real Agent Runtime -> Real HTTP Cloud API -> Real DB/Redis
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

echo "Using Python: $(${PYTHON_BIN} --version 2>&1) (${PYTHON_BIN})"

# 2. Verify Redis connectivity
REDIS_URL="${REDIS_URL:-redis://localhost:6379/14}"
echo "Checking Redis connectivity at ${REDIS_URL}..."
if command -v redis-cli &>/dev/null; then
    if ! redis-cli ping &>/dev/null; then
        echo "Redis not responding on default port, attempting daemon start..."
        if command -v redis-server &>/dev/null; then
            redis-server --daemonize yes || true
            sleep 1
        fi
    fi
fi

# 3. Ensure Database URL is configured
export POSTGRES_E2E_URL="${POSTGRES_E2E_URL:-${POSTGRES_TEST_URL:-postgresql+asyncpg://nuras@localhost:5432/poscenter_loyalty_e2e_test}}"
export PYTHONPATH="${REPO_ROOT}:${REPO_ROOT}/backend:${REPO_ROOT}/agent/src:${PYTHONPATH:-}"

echo "Database target: ${POSTGRES_E2E_URL}"
echo "Running Pre-ONE E2E test suite..."
echo "------------------------------------------------------------------------"

${PYTEST_BIN} -v -s -o asyncio_mode=auto e2e/test_pre_one_flow.py "$@"

EXIT_CODE=$?

echo "------------------------------------------------------------------------"
if [[ ${EXIT_CODE} -eq 0 ]]; then
    echo "SUCCESS: All Pre-ONE End-to-End integration scenarios passed."
else
    echo "FAILURE: Pre-ONE E2E tests failed with exit code ${EXIT_CODE}."
fi
echo "========================================================================"

exit ${EXIT_CODE}
