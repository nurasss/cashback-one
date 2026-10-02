#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# POSCENTER Loyalty Cloud - PostgreSQL Safe Restore Script
# ==============================================================================
# Usage:
#   ./scripts/restore_postgres.sh <backup_file> <target_database> [--confirm-overwrite]
#
# Environment variables:
#   PGHOST         - PostgreSQL host (default: localhost)
#   PGPORT         - PostgreSQL port (default: 5432)
#   PGUSER         - PostgreSQL user (default: postgres)
#   PGPASSWORD     - PostgreSQL password (handled securely in environment)
# ==============================================================================

if [ "$#" -lt 2 ]; then
    echo "Usage: $0 <backup_file> <target_database> [--confirm-overwrite]" >&2
    exit 1
fi

BACKUP_FILE="$1"
TARGET_DB="$2"
CONFIRM_FLAG="${3:-}"

PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-postgres}"

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "[ERROR] Backup file not found: ${BACKUP_FILE}" >&2
    exit 1
fi

# Step 1: Verify SHA-256 checksum if .sha256 file is present alongside backup
CHECKSUM_FILE="${BACKUP_FILE}.sha256"
if [ -f "${CHECKSUM_FILE}" ]; then
    echo "[INFO] Verifying backup checksum with ${CHECKSUM_FILE}..."
    BACKUP_DIR="$(dirname "${BACKUP_FILE}")"
    BASE_FILE="$(basename "${BACKUP_FILE}")"
    CHECKSUM_BASE="$(basename "${CHECKSUM_FILE}")"

    if command -v sha256sum >/dev/null 2>&1; then
        (cd "${BACKUP_DIR}" && sha256sum -c "${CHECKSUM_BASE}")
    elif command -v shasum >/dev/null 2>&1; then
        (cd "${BACKUP_DIR}" && shasum -a 256 -c "${CHECKSUM_BASE}")
    else
        echo "[ERROR] Neither sha256sum nor shasum is available to verify checksum." >&2
        exit 1
    fi
    echo "[SUCCESS] Checksum verification passed."
else
    echo "[WARNING] No .sha256 checksum file found next to ${BACKUP_FILE}."
fi

# Step 2: Safety confirmation to prevent accidental overwrites
if [ "${CONFIRM_FLAG}" != "--confirm-overwrite" ]; then
    echo "=================================================================="
    echo "CAUTION: This will overwrite data in database '${TARGET_DB}'!"
    echo "Host: ${PGHOST}:${PGPORT} | User: ${PGUSER}"
    echo "Source: ${BACKUP_FILE}"
    echo "=================================================================="
    read -r -p "Type 'RESTORE' to proceed with overwrite: " CONFIRMATION
    if [ "${CONFIRMATION}" != "RESTORE" ]; then
        echo "[ABORTED] Restore cancelled by user." >&2
        exit 1
    fi
fi

# Step 3: Verify target database connectivity before restoration
echo "[INFO] Verifying target database connectivity on ${PGHOST}:${PGPORT}/${TARGET_DB}..."
if ! psql --host="${PGHOST}" --port="${PGPORT}" --username="${PGUSER}" --dbname="${TARGET_DB}" -c "SELECT 1;" >/dev/null 2>&1; then
    echo "[ERROR] Cannot connect to target database '${TARGET_DB}' on ${PGHOST}:${PGPORT}." >&2
    exit 1
fi

# Step 4: Execute pg_restore
echo "[INFO] Restoring database '${TARGET_DB}' from '${BACKUP_FILE}'..."

RESTORE_EXIT=0
pg_restore \
    --host="${PGHOST}" \
    --port="${PGPORT}" \
    --username="${PGUSER}" \
    --dbname="${TARGET_DB}" \
    --clean \
    --if-exists \
    --no-owner \
    --no-privileges \
    --verbose \
    "${BACKUP_FILE}" || RESTORE_EXIT=$?

if [ "${RESTORE_EXIT}" -ne 0 ]; then
    echo "[ERROR] pg_restore failed with exit code ${RESTORE_EXIT}." >&2
    exit "${RESTORE_EXIT}"
fi

# Step 5: Post-restore verification (connectivity and schema migration version)
echo "[INFO] Verifying database integrity and schema version..."
if ! psql --host="${PGHOST}" --port="${PGPORT}" --username="${PGUSER}" --dbname="${TARGET_DB}" -c "SELECT 1;" >/dev/null 2>&1; then
    echo "[ERROR] Post-restore connectivity check failed for '${TARGET_DB}'." >&2
    exit 1
fi

ALEMBIC_VERSION=$(psql --host="${PGHOST}" --port="${PGPORT}" --username="${PGUSER}" --dbname="${TARGET_DB}" -t -A -c "SELECT version_num FROM alembic_version LIMIT 1;" 2>/dev/null || true)
if [ -z "${ALEMBIC_VERSION}" ]; then
    echo "[ERROR] Post-restore check failed: 'alembic_version' table is empty or missing in '${TARGET_DB}'." >&2
    exit 1
fi

echo "[SUCCESS] Restore completed successfully for '${TARGET_DB}'. Current schema version: ${ALEMBIC_VERSION}"
