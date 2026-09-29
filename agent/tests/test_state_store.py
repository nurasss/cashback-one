"""Tests for SQLite durable state store, schema versioning, and corruption handling."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from poscenter_loyalty_agent.state_store import (
    STATE_SCHEMA_VERSION,
    StateDbCorruptedError,
    StateSchemaUnsupportedError,
    StateStore,
)


def test_state_store_init_and_empty_status(tmp_path: Path) -> None:
    db_file = tmp_path / "state.db"
    store = StateStore(db_file)

    status = store.get_status()
    assert status.cards_committed_cursor is None
    assert status.transactions_committed_cursor is None
    assert status.last_successful_sync_at is None
    assert status.last_error is None
    assert status.last_heartbeat_at is None

    # Check user_version stamped
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    ver = cur.execute("PRAGMA user_version;").fetchone()[0]
    conn.close()
    assert ver == STATE_SCHEMA_VERSION


def test_state_store_reinit_idempotent(tmp_path: Path) -> None:
    db_file = tmp_path / "state.db"
    store1 = StateStore(db_file)
    store1.commit_cursor("cards", "c_1", synced_at=datetime.now(UTC))

    # Re-open database with new instance
    store2 = StateStore(db_file)
    assert store2.get_cursor("cards") == "c_1"


def test_legacy_version_0_upgrade(tmp_path: Path) -> None:
    """A pre-existing TASK-008 database with version 0 is safely recognized and upgraded to v1."""
    db_file = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(db_file))
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
    conn.execute("INSERT INTO agent_checkpoint (id, cards_committed_cursor, updated_at) VALUES (1, 'C123', '2026-01-01');")
    conn.execute("PRAGMA user_version = 0;")
    conn.commit()
    conn.close()

    # Opening with StateStore should safely upgrade user_version to 1
    store = StateStore(db_file)
    assert store.get_cursor("cards") == "C123"

    conn = sqlite3.connect(str(db_file))
    ver = conn.cursor().execute("PRAGMA user_version;").fetchone()[0]
    conn.close()
    assert ver == STATE_SCHEMA_VERSION


def test_foreign_sqlite_no_silent_mutation(tmp_path: Path) -> None:
    """An unrelated existing SQLite DB must NOT be mutated into an agent DB."""
    db_file = tmp_path / "foreign.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE unrelated (id INTEGER);")
    conn.execute("PRAGMA user_version = 0;")
    conn.commit()
    conn.close()

    with pytest.raises(StateSchemaUnsupportedError, match="STATE_SCHEMA_UNSUPPORTED"):
        StateStore(db_file)

    # Verify database was NOT mutated
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    tables = [row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
    ver = cur.execute("PRAGMA user_version;").fetchone()[0]
    conn.close()

    assert "agent_checkpoint" not in tables
    assert "unrelated" in tables
    assert ver == 0


def test_incompatible_checkpoint_structure_rejected(tmp_path: Path) -> None:
    """An existing agent_checkpoint missing required columns must be rejected without mutation."""
    db_file = tmp_path / "incompatible.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE agent_checkpoint (id INTEGER PRIMARY KEY);")
    conn.execute("PRAGMA user_version = 0;")
    conn.commit()
    conn.close()

    with pytest.raises(StateSchemaUnsupportedError, match="STATE_SCHEMA_UNSUPPORTED"):
        StateStore(db_file)


def test_unsupported_future_schema_version(tmp_path: Path) -> None:
    db_file = tmp_path / "future.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("PRAGMA user_version = 99;")
    conn.commit()
    conn.close()

    with pytest.raises(StateSchemaUnsupportedError, match="STATE_SCHEMA_UNSUPPORTED"):
        StateStore(db_file)


def test_corrupted_sqlite_file_handling(tmp_path: Path) -> None:
    db_file = tmp_path / "corrupted.db"
    # Write random invalid garbage bytes
    db_file.write_bytes(b"NOT_A_SQLITE_DATABASE_GARBAGE_BYTES_1234567890")

    with pytest.raises(StateDbCorruptedError, match="STATE_DB_CORRUPTED"):
        StateStore(db_file)

    # Corrupted file must NOT be deleted or overwritten
    assert db_file.exists()
    assert db_file.read_bytes().startswith(b"NOT_A_SQLITE")


def test_stream_argument_validation(tmp_path: Path) -> None:
    db_file = tmp_path / "state.db"
    store = StateStore(db_file)

    with pytest.raises(ValueError, match="Invalid stream"):
        store.get_cursor("unsupported_stream")

    with pytest.raises(ValueError, match="Invalid stream"):
        store.commit_cursor("unknown_stream", "c_val", synced_at=datetime.now(UTC))


def test_commit_and_get_cursors(tmp_path: Path) -> None:
    db_file = tmp_path / "state.db"
    store = StateStore(db_file)

    now = datetime(2026, 9, 29, 12, 0, 0, tzinfo=UTC)
    store.commit_cursor("cards", "card_offset_100", synced_at=now)
    assert store.get_cursor("cards") == "card_offset_100"
    assert store.get_cursor("transactions") is None

    store.commit_cursor("transactions", "tx_offset_50", synced_at=now)
    assert store.get_cursor("transactions") == "tx_offset_50"

    status = store.get_status()
    assert status.cards_committed_cursor == "card_offset_100"
    assert status.transactions_committed_cursor == "tx_offset_50"
    assert status.last_successful_sync_at == now


def test_record_error_sanitization_and_clear(tmp_path: Path) -> None:
    db_file = tmp_path / "state.db"
    store = StateStore(db_file)

    raw_error = "Connect failed with Usr=admin;Pwd=supersecret123; for card 1234567890123"
    error_time = datetime(2026, 9, 29, 12, 5, 0, tzinfo=UTC)
    store.record_error(raw_error, error_at=error_time)

    status = store.get_status()
    assert status.last_error is not None
    assert "supersecret123" not in status.last_error
    assert "***REDACTED***" in status.last_error
    assert "1234567890123" not in status.last_error
    assert "***BARCODE_REDACTED***" in status.last_error

    # Ensure zero secrets in raw SQLite
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    row = cur.execute("SELECT last_error FROM agent_checkpoint WHERE id = 1;").fetchone()
    assert "supersecret123" not in row[0]
    conn.close()

    # Clear error
    store.clear_error()
    status_cleared = store.get_status()
    assert status_cleared.last_error is None


def test_record_heartbeat(tmp_path: Path) -> None:
    db_file = tmp_path / "state.db"
    store = StateStore(db_file)

    hb_time = datetime(2026, 9, 29, 12, 10, 0, tzinfo=UTC)
    store.record_heartbeat(hb_time)

    status = store.get_status()
    assert status.last_heartbeat_at == hb_time
