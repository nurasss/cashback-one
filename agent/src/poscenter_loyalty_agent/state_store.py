"""Durable SQLite state store for checkpoint tracking and operational status.

Guarantees:
1. Zero PII stored: only opaque cursors, timestamps, and sanitized operational error strings.
2. Crash resilience: WAL mode, synchronous commits, atomic transactions.
3. At-least-once delivery support: cursor is only updated when explicitly committed after Cloud ACK.
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


class StateStore:
    """Manages persistent agent state in a local SQLite database."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize database schema if not present."""
        with self._get_connection() as conn:
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
            conn.commit()

    def get_cursor(self, stream: str) -> str | None:
        """Get the last committed cursor for 'cards' or 'transactions'."""
        column = "cards_committed_cursor" if stream == "cards" else "transactions_committed_cursor"
        with self._get_connection() as conn:
            cursor = conn.execute(f"SELECT {column} FROM agent_checkpoint WHERE id = 1;")
            row = cursor.fetchone()
            if row and row[column]:
                return str(row[column])
            return None

    def commit_cursor(self, stream: str, cursor_value: str | None, synced_at: datetime) -> None:
        """Persist new cursor and update last_successful_sync_at atomically."""
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
        logger.debug("Committed cursor for %s: %s (synced_at=%s)", stream, cursor_value, synced_iso)

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
