# PostgreSQL Backup and Disaster Recovery Runbook

This document defines the operational procedures for backing up and restoring the POSCENTER Loyalty Cloud PostgreSQL database.

---

## 1. Backup Strategy & Design

### Format
- Backups use `pg_dump` with custom binary format (`-Fc`).
- Format `-Fc` provides native gzip compression, is arch-independent, supports selective table/schema restores, and allows parallel restoration (`pg_restore -j`).

### Integrity & Security
- **Checksums**: Every backup file generates an adjacent `.sha256` checksum file immediately upon creation and is verified in-place.
- **Permissions**: Backups and checksum files are created with mode `0600` (readable and writable only by the backup service user), and the directory is set to `0700`.
- **Credentials**: Passwords are supplied strictly via the `PGPASSWORD` environment variable or standard `.pgpass` file with `0600` permissions. Passwords are never passed as command-line arguments to prevent credential exposure in `ps` process trees or audit logs.

---

## 2. Backup Execution

### Manual Backup
```bash
export PGHOST="localhost"
export PGPORT="5432"
export PGUSER="poscenter_app"
export PGPASSWORD="your-database-password"
export PGDATABASE="poscenter_loyalty"

./scripts/backup_postgres.sh ./backups/postgres
```

Output artifacts in `./backups/postgres`:
- `backup_poscenter_loyalty_20261003T010000Z.dump` (mode `0600`)
- `backup_poscenter_loyalty_20261003T010000Z.dump.sha256` (mode `0600`)

---

## 3. Automated Scheduling

### Cron Job (Daily at 02:00 UTC)
```crontab
0 2 * * * /opt/poscenter-loyalty/scripts/backup_postgres.sh /var/backups/poscenter >> /var/log/poscenter_backup.log 2>&1
```

### Systemd Service & Timer Example
`/etc/systemd/system/poscenter-backup.service`:
```ini
[Unit]
Description=POSCENTER Loyalty PostgreSQL Backup
After=postgresql.service

[Service]
Type=oneshot
User=postgres
Environment="PGHOST=127.0.0.1"
Environment="PGPORT=5432"
Environment="PGUSER=poscenter_app"
EnvironmentFile=/etc/poscenter/backup.env
ExecStart=/opt/poscenter-loyalty/scripts/backup_postgres.sh /var/backups/poscenter
```

`/etc/systemd/system/poscenter-backup.timer`:
```ini
[Unit]
Description=Run POSCENTER Loyalty PostgreSQL Backup Daily

[Timer]
OnCalendar=*-*-* 02:00:00 UTC
Persistent=true

[Install]
WantedBy=timers.target
```

---

## 4. Disaster Recovery & Restore Procedure

### Safety Requirements
1. The restore script automatically verifies the `.sha256` checksum of the backup file before initiating restoration. If checksum validation fails, execution aborts immediately.
2. An explicit `--confirm-overwrite` argument (or interactive prompt) is required to prevent accidental database overwrites.
3. Stop the application backend services or redirect traffic before performing a production database restore.

### Manual Verification of Checksum
```bash
sha256sum -c backup_poscenter_loyalty_20261003T010000Z.dump.sha256
# or on macOS:
shasum -a 256 -c backup_poscenter_loyalty_20261003T010000Z.dump.sha256
```

### Restore Execution
```bash
export PGHOST="localhost"
export PGPORT="5432"
export PGUSER="postgres"
export PGPASSWORD="your-admin-password"

# Interactive confirmation prompt:
./scripts/restore_postgres.sh ./backups/postgres/backup_poscenter_loyalty_20261003T010000Z.dump poscenter_loyalty

# Automated / non-interactive confirmation (for CI/CD or disaster recovery orchestration):
./scripts/restore_postgres.sh ./backups/postgres/backup_poscenter_loyalty_20261003T010000Z.dump poscenter_loyalty --confirm-overwrite
```

### Post-Restore Verification
1. Run application migrations to ensure schema revision parity:
   ```bash
   alembic upgrade head
   ```
2. Verify readiness endpoint:
   ```bash
   curl -i http://127.0.0.1:8000/health/ready
   ```
   Must return HTTP 200 OK with `status: ok` and all dependencies green.
