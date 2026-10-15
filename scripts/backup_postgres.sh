#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# POSCENTER Loyalty Cloud - PostgreSQL Automated Backup Script
# ==============================================================================
# Usage:
#   ./scripts/backup_postgres.sh [backup_dir]
#
# Environment variables:
#   PGHOST         - PostgreSQL host (default: localhost)
#   PGPORT         - PostgreSQL port (default: 5432)
#   PGUSER         - PostgreSQL user (default: postgres)
#   PGDATABASE     - PostgreSQL database name (default: poscenter_loyalty)
#   PGPASSWORD     - PostgreSQL password (handled securely in environment)
#   BACKUP_RETENTION_DAYS - Number of days to retain backups (default: 14)
# ==============================================================================

BACKUP_DIR="${1:-${BACKUP_DIR:-./backups/postgres}}"
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-postgres}"
PGDATABASE="${PGDATABASE:-poscenter_loyalty}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"

TIMESTAMP="$(date -u +"%Y%m%dT%H%M%SZ")"
FILENAME="backup_${PGDATABASE}_${TIMESTAMP}.dump"
TARGET_FILE="${BACKUP_DIR}/${FILENAME}"
CHECKSUM_FILE="${TARGET_FILE}.sha256"

mkdir -p "${BACKUP_DIR}"
chmod 700 "${BACKUP_DIR}"

echo "[INFO] Starting backup of database '${PGDATABASE}' from ${PGHOST}:${PGPORT}..."

# Execute pg_dump with custom format (-Fc), compressed and suitable for pg_restore
# Sensitive credentials are passed strictly via PGPASSWORD environment, never CLI arguments
pg_dump \
    --host="${PGHOST}" \
    --port="${PGPORT}" \
    --username="${PGUSER}" \
    --format=custom \
    --blobs \
    --verbose \
    --file="${TARGET_FILE}" \
    "${PGDATABASE}"

# Restrict file permissions immediately
chmod 600 "${TARGET_FILE}"

echo "[INFO] Generating SHA-256 integrity checksum..."
if command -v sha256sum >/dev/null 2>&1; then
    (cd "${BACKUP_DIR}" && sha256sum "${FILENAME}" > "${FILENAME}.sha256")
elif command -v shasum >/dev/null 2>&1; then
    (cd "${BACKUP_DIR}" && shasum -a 256 "${FILENAME}" > "${FILENAME}.sha256")
else
    echo "[ERROR] Neither sha256sum nor shasum is available to compute checksum." >&2
    exit 1
fi

chmod 600 "${CHECKSUM_FILE}"

# Verify checksum immediately after creation
echo "[INFO] Verifying backup checksum..."
if command -v sha256sum >/dev/null 2>&1; then
    (cd "${BACKUP_DIR}" && sha256sum -c "${FILENAME}.sha256")
else
    (cd "${BACKUP_DIR}" && shasum -a 256 -c "${FILENAME}.sha256")
fi

BACKUP_SIZE="$(ls -lh "${TARGET_FILE}" | awk '{print $5}')"
echo "[SUCCESS] Backup completed: ${TARGET_FILE} (Size: ${BACKUP_SIZE})"
echo "[SUCCESS] Checksum verified: ${CHECKSUM_FILE}"

# Optional automatic rotation of old backups
if [ -n "${RETENTION_DAYS}" ] && [ "${RETENTION_DAYS}" -gt 0 ]; then
    echo "[INFO] Rotating backups older than ${RETENTION_DAYS} days in ${BACKUP_DIR}..."
    find "${BACKUP_DIR}" -name "backup_${PGDATABASE}_*.dump" -mtime +"${RETENTION_DAYS}" -exec rm -f {} \;
    find "${BACKUP_DIR}" -name "backup_${PGDATABASE}_*.dump.sha256" -mtime +"${RETENTION_DAYS}" -exec rm -f {} \;
fi
