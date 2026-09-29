"""Tests for poscenter-loyalty-agent CLI commands."""

import argparse
from datetime import UTC, datetime
from pathlib import Path

import pytest

from poscenter_loyalty_agent.main import cmd_check_config, cmd_status
from poscenter_loyalty_agent.state_store import StateStore


def test_cli_check_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_file = tmp_path / "cli_state.db"
    monkeypatch.setenv("AGENT_API_KEY", "test-api-key-for-cli")
    monkeypatch.setenv("AGENT_STATE_DB_PATH", str(db_file))

    args = argparse.Namespace()
    exit_code = cmd_check_config(args)
    assert exit_code == 0
    assert db_file.exists()


def test_cli_status(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_file = tmp_path / "cli_state.db"
    store = StateStore(db_file)
    store.commit_cursor("cards", "super_secret_raw_cursor_12345", synced_at=datetime.now(UTC))
    store.record_error("Test CLI error")

    monkeypatch.setenv("AGENT_API_KEY", "test-api-key-for-cli")
    monkeypatch.setenv("AGENT_STATE_DB_PATH", str(db_file))

    args = argparse.Namespace()
    exit_code = cmd_status(args)
    assert exit_code == 0

    captured = capsys.readouterr().out
    assert "Cards Cursor Status:           set" in captured
    assert "Transactions Cursor Status:    (none)" in captured
    # Raw cursor is NOT leaked
    assert "super_secret_raw_cursor_12345" not in captured
