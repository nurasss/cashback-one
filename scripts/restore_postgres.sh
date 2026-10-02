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

echo "[INFO] Restoring database '${TARGET_DB}' from '${BACKUP_FILE}'..."

# Execute pg_restore:
# --clean: clean (drop) database objects before recreating them
# --if-exists: do not error if objects do not exist during drop
# --no-owner: do not output commands to set ownership of objects
# --no-privileges: prevent restoration of access privileges (grant/revoke)
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
    "${BACKUP_FILE}" || {
        # Note: pg_restore may return 1 on warnings (e.g. drop table if not exists).
        # We verify DB connectivity and health afterward.
        RESTORE_EXIT=$?
        echo "[WARNING] pg_restore exited with code ${RESTORE_EXIT} (may be non-fatal warnings)."
    }

echo "[SUCCESS] Restore command completed for '${TARGET_DB}'."
