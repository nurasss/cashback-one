"""Tests for poscenter-loyalty-agent CLI commands."""

import argparse
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from poscenter_loyalty_agent.main import cmd_check_config, cmd_run, cmd_status
from poscenter_loyalty_agent.state_store import StateStore


def test_cli_check_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_file = tmp_path / "cli_state.db"
    monkeypatch.setenv("AGENT_API_KEY", "test-api-key-for-cli")
    monkeypatch.setenv("AGENT_STATE_DB_PATH", str(db_file))
    monkeypatch.setenv("AGENT_LOG_MAX_BYTES", "123456")
    monkeypatch.setenv("AGENT_LOG_BACKUP_COUNT", "7")

    args = argparse.Namespace()
    exit_code = cmd_check_config(args)
    assert exit_code == 0
    assert db_file.exists()

    captured = capsys.readouterr().out
    assert "Log Rotation Max Bytes: 123456" in captured
    assert "Log Backup Count:       7" in captured


def test_cli_run_log_rotation_config_forwarding(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Settings log_max_bytes and log_backup_count must be passed to configure_logging."""
    db_file = tmp_path / "cli_run.db"
    monkeypatch.setenv("AGENT_API_KEY", "test-api-key-for-cli")
    monkeypatch.setenv("AGENT_STATE_DB_PATH", str(db_file))
    monkeypatch.setenv("AGENT_LOG_MAX_BYTES", "123456")
    monkeypatch.setenv("AGENT_LOG_BACKUP_COUNT", "7")

    captured_kwargs: dict[str, object] = {}

    def fake_configure_logging(**kwargs: object) -> None:
        captured_kwargs.update(kwargs)

    with patch("poscenter_loyalty_agent.main.configure_logging", side_effect=fake_configure_logging), \
         patch("poscenter_loyalty_agent.main.AgentRuntime") as mock_runtime_cls:
        mock_runtime = mock_runtime_cls.return_value
        mock_runtime.run = AsyncMock()

        exit_code = cmd_run(argparse.Namespace())
        assert exit_code == 0

    assert captured_kwargs.get("max_bytes") == 123456
    assert captured_kwargs.get("backup_count") == 7


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
