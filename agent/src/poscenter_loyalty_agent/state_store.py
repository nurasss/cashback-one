"""Durable SQLite state store for checkpoint tracking and operational status.

Guarantees:
1. Zero PII stored: only opaque cursors, timestamps, and sanitized operational error strings.
2. Crash resilience: WAL mode, synchronous commits, atomic transactions.
3. At-least-once delivery support: cursor is only updated when explicitly committed after Cloud ACK.
4. Schema versioning and corruption defense: detects corrupted files and unsupported schema versions.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from poscenter_loyalty_agent.logging import sanitize_message
from poscenter_loyalty_agent.models import AgentStatus

logger = logging.getLogger(__name__)

STATE_SCHEMA_VERSION = 1
VALID_STREAMS = ("cards", "transactions")


class StateStoreError(Exception):
    """Base error for state store operations."""


class StateSchemaUnsupportedError(StateStoreError):
    """Raised when SQLite schema version is newer than supported or incompatible."""


class StateDbCorruptedError(StateStoreError):
    """Raised when SQLite database file is corrupted or not a valid database."""


class StateStore:
    """Manages persistent agent state in a local SQLite database."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=30.0)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.DatabaseError as exc:
            raise StateDbCorruptedError(f"STATE_DB_CORRUPTED: Failed to connect to SQLite: {exc}") from exc

    def _init_db(self) -> None:
        """Initialize database schema, verify integrity and schema version."""
        # If file already exists and is non-empty, check for corruption
        if self.db_path.exists() and self.db_path.stat().st_size > 0:
            try:
                with sqlite3.connect(str(self.db_path), timeout=30.0) as test_conn:
                    cur = test_conn.execute("PRAGMA quick_check;")
                    row = cur.fetchone()
                    if not row or row[0] != "ok":
                        raise StateDbCorruptedError(
                            f"STATE_DB_CORRUPTED: SQLite integrity check failed: {row[0] if row else 'empty'}"
                        )
            except sqlite3.DatabaseError as exc:
                raise StateDbCorruptedError(f"STATE_DB_CORRUPTED: Corrupted SQLite database file: {exc}") from exc

        conn = self._get_connection()
        try:
            with conn:
                # Check user_version
                cur = conn.execute("PRAGMA user_version;")
                row = cur.fetchone()
                current_ver = row[0] if row else 0

                if current_ver > STATE_SCHEMA_VERSION:
                    raise StateSchemaUnsupportedError(
                        f"STATE_SCHEMA_UNSUPPORTED: Database schema version {current_ver} "
                        f"is newer than supported version {STATE_SCHEMA_VERSION}."
                    )

                # Create table if not present
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS agent_checkpoint (
                        id INTEGER PRIMARY KEY CHECK (id = 1),
                        cards_committed_cursor TEXT,
                        transactions_committed_cursor TEXT,
                        last_successful_sync_at TEXT,
                        last_error TEXT,
                        last_error_at TEXT,
                        last_heartbeat_at TEXT,
                        updated_at TEXT NOT NULL
                    );
                    """
                )

                # Ensure row with id=1 exists
                now_iso = datetime.now(UTC).isoformat()
                conn.execute(
                    """
                    INSERT OR IGNORE INTO agent_checkpoint (id, updated_at)
                    VALUES (1, ?);
                    """,
                    (now_iso,),
                )

                # If migrating from v0 or creating new, stamp schema version
                if current_ver < STATE_SCHEMA_VERSION:
                    conn.execute(f"PRAGMA user_version = {STATE_SCHEMA_VERSION};")
                    logger.info("Stamped agent_state.db schema to version %d", STATE_SCHEMA_VERSION)
        except sqlite3.DatabaseError as exc:
            raise StateDbCorruptedError(f"STATE_DB_CORRUPTED: Failed initializing schema: {exc}") from exc
        finally:
            conn.close()

    def get_cursor(self, stream: str) -> str | None:
        """Get the last committed cursor for 'cards' or 'transactions'."""
        if stream not in VALID_STREAMS:
            raise ValueError(f"Invalid stream '{stream}'. Allowed: {VALID_STREAMS}")

        column = "cards_committed_cursor" if stream == "cards" else "transactions_committed_cursor"
        with self._get_connection() as conn:
            cursor = conn.execute(f"SELECT {column} FROM agent_checkpoint WHERE id = 1;")
            row = cursor.fetchone()
            if row and row[column]:
                return str(row[column])
            return None

    def commit_cursor(self, stream: str, cursor_value: str | None, synced_at: datetime) -> None:
        """Persist new cursor and update last_successful_sync_at atomically."""
        if stream not in VALID_STREAMS:
            raise ValueError(f"Invalid stream '{stream}'. Allowed: {VALID_STREAMS}")

        column = "cards_committed_cursor" if stream == "cards" else "transactions_committed_cursor"
        synced_iso = synced_at.isoformat()
        now_iso = datetime.now(UTC).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                f"""
                UPDATE agent_checkpoint
                SET {column} = ?,
                    last_successful_sync_at = ?,
                    last_error = NULL,
                    last_error_at = NULL,
                    updated_at = ?
                WHERE id = 1;
                """,
                (cursor_value, synced_iso, now_iso),
            )
            conn.commit()
        # Zero raw cursor logged
        logger.debug("Committed %s cursor checkpoint (synced_at=%s)", stream, synced_iso)

    def record_error(self, error_message: str, error_at: datetime | None = None) -> None:
        """Record operational error (sanitized to remove any secrets/PII)."""
        if error_at is None:
            error_at = datetime.now(UTC)
        sanitized = sanitize_message(error_message)[:1000]
        error_iso = error_at.isoformat()
        now_iso = datetime.now(UTC).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE agent_checkpoint
                SET last_error = ?,
                    last_error_at = ?,
                    updated_at = ?
                WHERE id = 1;
                """,
                (sanitized, error_iso, now_iso),
            )
            conn.commit()
        logger.warning("Recorded error in state store: %s", sanitized)

    def clear_error(self) -> None:
        """Clear error status on recovery."""
        now_iso = datetime.now(UTC).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE agent_checkpoint
                SET last_error = NULL,
                    last_error_at = NULL,
                    updated_at = ?
                WHERE id = 1;
                """,
                (now_iso,),
            )
            conn.commit()

    def record_heartbeat(self, heartbeat_at: datetime | None = None) -> None:
        """Record timestamp of successful heartbeat."""
        if heartbeat_at is None:
            heartbeat_at = datetime.now(UTC)
        heartbeat_iso = heartbeat_at.isoformat()
        now_iso = datetime.now(UTC).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE agent_checkpoint
                SET last_heartbeat_at = ?,
                    updated_at = ?
                WHERE id = 1;
                """,
                (heartbeat_iso, now_iso),
            )
            conn.commit()

    def get_status(self) -> AgentStatus:
        """Retrieve full operational checkpoint status."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM agent_checkpoint WHERE id = 1;")
            row = cursor.fetchone()
            if not row:
                return AgentStatus()

            def _parse_dt(val: Any) -> datetime | None:
                if not val:
                    return None
                try:
                    return datetime.fromisoformat(val)
                except (ValueError, TypeError):
                    return None

            return AgentStatus(
                cards_committed_cursor=row["cards_committed_cursor"],
                transactions_committed_cursor=row["transactions_committed_cursor"],
                last_successful_sync_at=_parse_dt(row["last_successful_sync_at"]),
                last_error=row["last_error"],
                last_error_at=_parse_dt(row["last_error_at"]),
                last_heartbeat_at=_parse_dt(row["last_heartbeat_at"]),
            )
