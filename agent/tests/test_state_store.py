"""Tests for SQLite durable state store."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from poscenter_loyalty_agent.state_store import StateStore


def test_state_store_init_and_empty_status(tmp_path: Path) -> None:
    db_file = tmp_path / "state.db"
    store = StateStore(db_file)

    status = store.get_status()
    assert status.cards_committed_cursor is None
    assert status.transactions_committed_cursor is None
    assert status.last_successful_sync_at is None
    assert status.last_error is None
    assert status.last_heartbeat_at is None


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

    # Error message containing secret and PII
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
