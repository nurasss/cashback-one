"""Durable SQLite state store for checkpoint tracking and operational status.

Guarantees:
1. Zero PII stored: only opaque cursors, timestamps, and sanitized operational error strings.
2. Crash resilience: WAL mode, synchronous commits, atomic transactions.
3. At-least-once delivery support: cursor is only updated when explicitly committed after Cloud ACK.
4. Schema versioning and corruption defense: detects corrupted files and unsupported schema versions.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from poscenter_loyalty_agent.logging import sanitize_message
from poscenter_loyalty_agent.models import AgentStatus

logger = logging.getLogger(__name__)

STATE_SCHEMA_VERSION = 2
VALID_STREAMS = ("cards", "transactions")


class StateStoreError(Exception):
    """Base error for state store operations."""


class StateSchemaUnsupportedError(StateStoreError):
    """Raised when SQLite schema version is newer than supported or incompatible."""


class StateDbNotAgentDatabaseError(StateSchemaUnsupportedError):
    """Raised when existing SQLite DB is not a valid Agent state store."""

    def __init__(self, message: str = "STATE_SCHEMA_UNSUPPORTED: Existing SQLite database is not an agent database.") -> None:
        super().__init__(message)
        self.code = "STATE_SCHEMA_UNSUPPORTED"


class StateDbCorruptedError(StateStoreError):
    """Raised when SQLite database file is corrupted or not a valid database."""


REQUIRED_CHECKPOINT_COLUMNS = frozenset({
    "id",
    "cards_committed_cursor",
    "transactions_committed_cursor",
    "last_successful_sync_at",
    "last_error",
    "last_error_at",
    "last_heartbeat_at",
    "updated_at",
})


class StateStore:
    """Manages persistent agent state in a local SQLite database."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._init_db()

    def _open_readonly_connection(self) -> sqlite3.Connection:
        """Open an existing database in strictly read-only mode using SQLite URI."""
        resolved = self.db_path.resolve()
        db_uri = f"file:{resolved.as_posix()}?mode=ro"
        conn = sqlite3.connect(db_uri, uri=True, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _open_agent_writable_connection(self) -> sqlite3.Connection:
        """Open or create the agent database with WAL journal mode and standard pragmas."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=30.0)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.DatabaseError as exc:
            raise StateDbCorruptedError(f"STATE_DB_CORRUPTED: Failed to connect to SQLite: {exc}") from exc

    def _get_connection(self) -> sqlite3.Connection:
        return self._open_agent_writable_connection()

    def _init_db(self) -> None:
        """Initialize database schema, verify integrity and schema version."""
        file_exists = self.db_path.exists()
        is_non_empty = file_exists and self.db_path.stat().st_size > 0

        # Case A & B: New database file (absent or 0 bytes)
        if not file_exists or not is_non_empty:
            conn = self._open_agent_writable_connection()
            try:
                with conn:
                    conn.execute(
                        """
                        CREATE TABLE agent_checkpoint (
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
                    conn.execute(
                        """
                        CREATE TABLE card_hashes (
                            card_ref_uuid TEXT PRIMARY KEY,
                            content_hash TEXT NOT NULL,
                            last_updated_at TEXT NOT NULL
                        );
                        """
                    )
                    conn.execute("CREATE INDEX idx_card_hashes_updated ON card_hashes(last_updated_at);")
                    conn.execute(
                        """
                        CREATE TABLE tx_ledger (
                            external_id TEXT PRIMARY KEY,
                            period_utc TEXT NOT NULL,
                            committed_at TEXT NOT NULL
                        );
                        """
                    )
                    conn.execute("CREATE INDEX idx_tx_ledger_period ON tx_ledger(period_utc);")
                    conn.execute(
                        """
                        CREATE TABLE pending_cards (
                            session_id TEXT NOT NULL,
                            page INTEGER NOT NULL,
                            card_ref_uuid TEXT NOT NULL,
                            content_hash TEXT NOT NULL,
                            last_updated_at TEXT NOT NULL,
                            PRIMARY KEY (session_id, card_ref_uuid)
                        );
                        """
                    )
                    conn.execute(
                        """
                        CREATE TABLE pending_tx (
                            token TEXT NOT NULL,
                            external_id TEXT NOT NULL,
                            period_utc TEXT NOT NULL,
                            PRIMARY KEY (token, external_id)
                        );
                        """
                    )
                    now_iso = datetime.now(UTC).isoformat()
                    conn.execute(
                        """
                        INSERT INTO agent_checkpoint (id, updated_at)
                        VALUES (1, ?);
                        """,
                        (now_iso,),
                    )
                    conn.execute(f"PRAGMA user_version = {STATE_SCHEMA_VERSION};")
                    logger.info("Stamped agent_state.db schema to version %d", STATE_SCHEMA_VERSION)
            except sqlite3.DatabaseError as exc:
                raise StateDbCorruptedError(f"STATE_DB_CORRUPTED: Failed initializing schema: {exc}") from exc
            finally:
                conn.close()
            return

        # Case C, D, E, F: Existing non-empty SQLite database
        # Phase 1: STRICT READ-ONLY INSPECTION (zero writes, no journal_mode change)
        try:
            ro_conn = self._open_readonly_connection()
        except sqlite3.DatabaseError as exc:
            raise StateDbCorruptedError(f"STATE_DB_CORRUPTED: Corrupted SQLite database file: {exc}") from exc

        try:
            with ro_conn:
                # 1. Integrity check
                cur = ro_conn.execute("PRAGMA quick_check;")
                row = cur.fetchone()
                if not row or row[0] != "ok":
                    raise StateDbCorruptedError(
                        f"STATE_DB_CORRUPTED: SQLite integrity check failed: {row[0] if row else 'empty'}"
                    )

                # 2. Check user_version
                cur = ro_conn.execute("PRAGMA user_version;")
                row = cur.fetchone()
                current_ver = row[0] if row else 0

                # Case F: Future schema version
                if current_ver > STATE_SCHEMA_VERSION:
                    raise StateSchemaUnsupportedError(
                        f"STATE_SCHEMA_UNSUPPORTED: Database schema version {current_ver} "
                        f"is newer than supported version {STATE_SCHEMA_VERSION}."
                    )

                # 3. Check existing tables
                cur = ro_conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
                )
                existing_tables = {r[0] for r in cur.fetchall()}

                # Case E: Foreign SQLite (no agent_checkpoint table)
                if "agent_checkpoint" not in existing_tables:
                    raise StateDbNotAgentDatabaseError(
                        "STATE_SCHEMA_UNSUPPORTED: Existing SQLite database does not contain "
                        "agent_checkpoint table (refusing to mutate unrelated database)."
                    )

                # 4. Check agent_checkpoint table structure
                cur = ro_conn.execute("PRAGMA table_info(agent_checkpoint);")
                actual_columns = {r["name"] for r in cur.fetchall()}
                missing = REQUIRED_CHECKPOINT_COLUMNS - actual_columns
                if missing:
                    raise StateSchemaUnsupportedError(
                        f"STATE_SCHEMA_UNSUPPORTED: Existing agent_checkpoint table missing required columns: {missing}"
                    )
        except (StateStoreError, sqlite3.DatabaseError) as exc:
            if isinstance(exc, StateStoreError):
                raise
            raise StateDbCorruptedError(f"STATE_DB_CORRUPTED: Corrupted SQLite database file: {exc}") from exc
        finally:
            ro_conn.close()

        # Phase 2: Verified Agent DB -> Writable Connection & Migration
        conn = self._open_agent_writable_connection()
        try:
            with conn:
                # Ensure row with id=1 exists
                now_iso = datetime.now(UTC).isoformat()
                conn.execute(
                    """
                    INSERT OR IGNORE INTO agent_checkpoint (id, updated_at)
                    VALUES (1, ?);
                    """,
                    (now_iso,),
                )

                # Phase 2 tables migration: create card_hashes, tx_ledger, pending tables
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS card_hashes (
                        card_ref_uuid TEXT PRIMARY KEY,
                        content_hash TEXT NOT NULL,
                        last_updated_at TEXT NOT NULL
                    );
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_card_hashes_updated ON card_hashes(last_updated_at);")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS tx_ledger (
                        external_id TEXT PRIMARY KEY,
                        period_utc TEXT NOT NULL,
                        committed_at TEXT NOT NULL
                    );
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_tx_ledger_period ON tx_ledger(period_utc);")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS pending_cards (
                        session_id TEXT NOT NULL,
                        page INTEGER NOT NULL,
                        card_ref_uuid TEXT NOT NULL,
                        content_hash TEXT NOT NULL,
                        last_updated_at TEXT NOT NULL,
                        PRIMARY KEY (session_id, card_ref_uuid)
                    );
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS pending_tx (
                        token TEXT NOT NULL,
                        external_id TEXT NOT NULL,
                        period_utc TEXT NOT NULL,
                        PRIMARY KEY (token, external_id)
                    );
                    """
                )

                # Stamp version
                if current_ver < STATE_SCHEMA_VERSION:
                    conn.execute(f"PRAGMA user_version = {STATE_SCHEMA_VERSION};")
                    logger.info("Upgraded agent_state.db schema to version %d", STATE_SCHEMA_VERSION)
        except sqlite3.DatabaseError as exc:
            raise StateDbCorruptedError(f"STATE_DB_CORRUPTED: Failed updating agent schema: {exc}") from exc
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

    # --- Card Hashes & Pending Cards API (Principle: "Фиксация по ACK") ---

    def get_card_hashes(self) -> dict[str, tuple[str, str]]:
        """Return all persisted card hashes: {card_ref_uuid: (content_hash, last_updated_at)}."""
        with self._get_connection() as conn:
            cur = conn.execute("SELECT card_ref_uuid, content_hash, last_updated_at FROM card_hashes;")
            return {row["card_ref_uuid"]: (row["content_hash"], row["last_updated_at"]) for row in cur.fetchall()}

    def record_pending_cards(self, session_id: str, page: int, cards: list[tuple[str, str, str]]) -> None:
        """Stage pending cards issued in a batch.

        CRITICAL ARCHITECTURAL GUARANTEE:
        These staged hashes are NOT committed to card_hashes until the next fetch
        proves that the caller successfully received and ACKed this page.
        """
        if not cards:
            return
        with self._get_connection() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO pending_cards (session_id, page, card_ref_uuid, content_hash, last_updated_at)
                VALUES (?, ?, ?, ?, ?);
                """,
                [(session_id, page, ref, ch, lu) for ref, ch, lu in cards],
            )
            conn.commit()

    def commit_pending_cards(self, session_id: str, page: int | None = None) -> int:
        """Promote staged pending cards to card_hashes upon receiving cursor proof of Cloud ACK.

        Uncompleted pending entries from prior crashes are safely applied if the cursor proves
        the batch was ACKed, or dropped if a new scan cycle starts.
        """
        with self._get_connection() as conn:
            if page is not None:
                cur = conn.execute(
                    "SELECT card_ref_uuid, content_hash, last_updated_at FROM pending_cards WHERE session_id = ? AND page <= ?;",
                    (session_id, page),
                )
            else:
                cur = conn.execute(
                    "SELECT card_ref_uuid, content_hash, last_updated_at FROM pending_cards WHERE session_id = ?;",
                    (session_id,),
                )
            rows = cur.fetchall()
            if not rows:
                return 0
            conn.executemany(
                """
                INSERT OR REPLACE INTO card_hashes (card_ref_uuid, content_hash, last_updated_at)
                VALUES (?, ?, ?);
                """,
                [(r["card_ref_uuid"], r["content_hash"], r["last_updated_at"]) for r in rows],
            )
            if page is not None:
                conn.execute("DELETE FROM pending_cards WHERE session_id = ? AND page <= ?;", (session_id, page))
            else:
                conn.execute("DELETE FROM pending_cards WHERE session_id = ?;", (session_id,))
            conn.commit()
            return len(rows)

    def clear_pending_cards(self, session_id: str | None = None) -> None:
        """Clear unconfirmed pending cards (e.g. after crash or when a new scan starts)."""
        with self._get_connection() as conn:
            if session_id:
                conn.execute("DELETE FROM pending_cards WHERE session_id = ?;", (session_id,))
            else:
                conn.execute("DELETE FROM pending_cards;")
            conn.commit()

    # --- Transaction Ledger & Pending Tx API ---

    def get_known_tx_ids(self, since_period_utc: str | None = None) -> set[str]:
        """Return set of external_ids that have already been confirmed in Cloud."""
        with self._get_connection() as conn:
            if since_period_utc:
                cur = conn.execute("SELECT external_id FROM tx_ledger WHERE period_utc >= ?;", (since_period_utc,))
            else:
                cur = conn.execute("SELECT external_id FROM tx_ledger;")
            return {row["external_id"] for row in cur.fetchall()}

    def record_pending_tx(self, token: str, txs: list[tuple[str, str]]) -> None:
        """Stage pending transactions issued in a batch.

        Transactions are NOT marked as committed in tx_ledger until the caller's next
        cursor proves that Cloud accepted this batch.
        """
        if not txs:
            return
        with self._get_connection() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO pending_tx (token, external_id, period_utc)
                VALUES (?, ?, ?);
                """,
                [(token, ext_id, period) for ext_id, period in txs],
            )
            conn.commit()

    def commit_pending_tx(self, token: str, committed_at: datetime | None = None) -> int:
        """Promote staged transactions to tx_ledger upon receiving cursor proof of Cloud ACK.

        Uncompleted pending entries from prior crashes are safely applied if the cursor matches,
        or pruned during sliding window maintenance.
        """
        committed_iso = (committed_at or datetime.now(UTC)).isoformat()
        with self._get_connection() as conn:
            cur = conn.execute("SELECT external_id, period_utc FROM pending_tx WHERE token = ?;", (token,))
            rows = cur.fetchall()
            if not rows:
                return 0
            conn.executemany(
                """
                INSERT OR IGNORE INTO tx_ledger (external_id, period_utc, committed_at)
                VALUES (?, ?, ?);
                """,
                [(r["external_id"], r["period_utc"], committed_iso) for r in rows],
            )
            conn.execute("DELETE FROM pending_tx WHERE token = ?;", (token,))
            conn.commit()
            return len(rows)

    def prune_tx_ledger(self, before_period_utc: str) -> int:
        """Prune records older than the sliding lookback window to prevent unbounded growth."""
        with self._get_connection() as conn:
            cur = conn.execute("DELETE FROM tx_ledger WHERE period_utc < ?;", (before_period_utc,))
            conn.execute("DELETE FROM pending_tx WHERE period_utc < ?;", (before_period_utc,))
            conn.commit()
            return cur.rowcount


def get_or_create_state_key(key_path: Path) -> bytes:
    """Retrieve existing 256-bit secret key or generate and securely persist a new one.

    Key bytes and path contents are strictly secret and must never be logged.
    """
    if key_path.exists():
        data = key_path.read_bytes()
        if len(data) >= 32:
            return data[:32]
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key = os.urandom(32)
    tmp_path = key_path.with_suffix(".tmp")
    tmp_path.write_bytes(key)
    tmp_path.replace(key_path)
    return key


def compute_card_hmac(key: bytes, message: str) -> str:
    """Compute HMAC-SHA256 hex digest for card state payload without leaking PII."""
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).hexdigest()

