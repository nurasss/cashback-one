#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# POSCENTER Loyalty Cloud - Production Smoke Verification Script
# ==============================================================================
# Verifies health/readiness, reverse proxy headers, Admin SPA navigation,
# and API 404 JSON isolation.
#
# Usage:
#   ./scripts/prod_smoke_check.sh [base_url]
#
# Example:
#   ./scripts/prod_smoke_check.sh http://127.0.0.1:8080
# ==============================================================================

BASE_URL="${1:-http://127.0.0.1:8080}"
BASE_URL="${BASE_URL%/}"

echo "=================================================================="
echo "Running Production Smoke Verification against: ${BASE_URL}"
echo "=================================================================="

FAILED=0

check_endpoint() {
    local name="$1"
    local path="$2"
    local expected_code="$3"
    local accept_header="$4"
    local expect_json="$5"

    echo -n "[TEST] ${name} (${path})... "
    
    local headers_file
    local body_file
    headers_file="$(mktemp)"
    body_file="$(mktemp)"

    local curl_opts=(-s -S -D "${headers_file}" -o "${body_file}")
    if [ -n "${accept_header}" ]; then
        curl_opts+=(-H "Accept: ${accept_header}")
    fi

    local status_code
    status_code="$(curl "${curl_opts[@]}" -w "%{http_code}" "${BASE_URL}${path}" || echo "000")"

    if [ "${status_code}" != "${expected_code}" ]; then
        echo "FAILED (Expected ${expected_code}, got ${status_code})"
        cat "${body_file}" >&2
        rm -f "${headers_file}" "${body_file}"
        FAILED=$((FAILED + 1))
        return 1
    fi

    if [ "${expect_json}" = "true" ]; then
        if grep -qi "text/html" "${headers_file}"; then
            echo "FAILED (Expected JSON response, but Content-Type was HTML)"
            cat "${body_file}" >&2
            rm -f "${headers_file}" "${body_file}"
            FAILED=$((FAILED + 1))
            return 1
        fi
        if ! grep -q "{" "${body_file}"; then
            echo "FAILED (Response body is not JSON)"
            rm -f "${headers_file}" "${body_file}"
            FAILED=$((FAILED + 1))
            return 1
        fi
    fi

    # Verify X-Request-ID presence on responses
    if ! grep -qi "X-Request-ID:" "${headers_file}"; then
        echo "WARNING (X-Request-ID header missing from response)"
    fi

    echo "PASSED (HTTP ${status_code})"
    rm -f "${headers_file}" "${body_file}"
    return 0
}

# 1. Liveness check: process is up (does not touch DB/Redis)
check_endpoint "Liveness probe" "/health/live" "200" "application/json" "true"

# 2. Readiness check: DB, Redis, and schema migration are verified
check_endpoint "Readiness probe" "/health/ready" "200" "application/json" "true"

# 3. Frontend root SPA loads HTML
check_endpoint "Admin root SPA" "/" "200" "text/html,application/xhtml+xml" "false"

# 4. Admin SPA direct navigation / refresh on /admin/businesses loads HTML
check_endpoint "Admin SPA direct route (/admin/businesses)" "/admin/businesses" "200" "text/html,application/xhtml+xml" "false"

# 5. Strict API 404 isolation: missing agent route returns JSON 404, NEVER HTML
check_endpoint "API missing route isolation (/agent/nonexistent)" "/agent/nonexistent" "404" "application/json" "true"

# 6. Strict API 404 isolation: missing customer auth route returns JSON 404
check_endpoint "API missing route isolation (/auth/nonexistent)" "/auth/nonexistent" "404" "application/json" "true"

# 7. Strict API 404 isolation: missing customer wallet route returns JSON 404
check_endpoint "API missing route isolation (/me/nonexistent)" "/me/nonexistent" "404" "application/json" "true"

echo "=================================================================="
if [ "${FAILED}" -eq 0 ]; then
    echo "ALL PRODUCTION SMOKE CHECKS PASSED!"
    echo "=================================================================="
    exit 0
else
    echo "SMOKE CHECKS FAILED: ${FAILED} failure(s) detected."
    echo "=================================================================="
    exit 1
fi
