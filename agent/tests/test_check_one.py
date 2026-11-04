"""Unit tests for check-one 1C infobase connection verifier."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import time
import types
from pathlib import Path
from typing import Any

import pytest

from poscenter_loyalty_agent.main import build_parser, cmd_check_one
from poscenter_loyalty_agent.one_check import (
    check_one_connection,
    classify_error,
    set_test_connector_factory,
)


@pytest.fixture(autouse=True)
def _reset_connector_factory():
    set_test_connector_factory(None)
    yield
    set_test_connector_factory(None)


def test_classify_error_mapping() -> None:
    assert classify_error(RuntimeError("Неверные имя пользователя или пароль")) == "auth_failed"
    assert classify_error(RuntimeError("Ошибка аутентификации")) == "auth_failed"
    assert classify_error(RuntimeError("Authentication failed")) == "auth_failed"
    assert classify_error(RuntimeError("База данных заблокирована")) == "db_locked"
    assert classify_error(RuntimeError("Ошибка исключительной блокировки")) == "db_locked"
    assert classify_error(RuntimeError("Информационная база не найдена")) == "db_not_found"
    assert classify_error(RuntimeError("Файл не найден: 1Cv8.1CD")) == "db_not_found"
    assert classify_error(RuntimeError("Invalid class string")) == "com_not_registered"
    assert classify_error(RuntimeError("Class not registered")) == "com_not_registered"
    assert classify_error(RuntimeError("Неизвестный сбой 0x80004005")) == "unknown"


def test_check_one_db_not_found_when_dir_missing(tmp_path: Path) -> None:
    nonexistent = tmp_path / "does_not_exist"
    code = check_one_connection(str(nonexistent), "user", "pass")
    assert code == "db_not_found"


def test_check_one_db_not_found_when_1cd_missing(tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty_base"
    empty_dir.mkdir()
    code = check_one_connection(str(empty_dir), "user", "pass")
    assert code == "db_not_found"


def test_check_one_ok(tmp_path: Path) -> None:
    base_dir = tmp_path / "valid_base"
    base_dir.mkdir()
    (base_dir / "1Cv8.1CD").write_bytes(b"dummy")

    class MockConnection:
        pass

    set_test_connector_factory(lambda conn_str: MockConnection())
    code = check_one_connection(str(base_dir), "user", "pass")
    assert code == "ok"


def test_check_one_auth_failed(tmp_path: Path) -> None:
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    (base_dir / "1Cv8.1CD").write_bytes(b"dummy")

    def mock_factory(conn_str: str) -> Any:
        raise RuntimeError("Неверные имя пользователя или пароль")

    set_test_connector_factory(mock_factory)
    code = check_one_connection(str(base_dir), "user", "wrong_pass")
    assert code == "auth_failed"


def test_check_one_db_locked(tmp_path: Path) -> None:
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    (base_dir / "1Cv8.1CD").write_bytes(b"dummy")

    def mock_factory(conn_str: str) -> Any:
        raise RuntimeError("База данных заблокирована монопольно")

    set_test_connector_factory(mock_factory)
    code = check_one_connection(str(base_dir), "user", "pass")
    assert code == "db_locked"


def test_check_one_timeout(tmp_path: Path) -> None:
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    (base_dir / "1Cv8.1CD").write_bytes(b"dummy")

    def hanging_factory(conn_str: str) -> Any:
        time.sleep(2.0)
        return object()

    set_test_connector_factory(hanging_factory)
    code = check_one_connection(str(base_dir), "user", "pass", timeout_seconds=0.1)
    assert code == "timeout"


def test_check_one_unknown_error(tmp_path: Path) -> None:
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    (base_dir / "1Cv8.1CD").write_bytes(b"dummy")

    def failing_factory(conn_str: str) -> Any:
        raise RuntimeError("Something completely unhandled occurred")

    set_test_connector_factory(failing_factory)
    code = check_one_connection(str(base_dir), "user", "pass")
    assert code == "unknown"


def test_cli_check_one_takes_password_from_env_never_args(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    (base_dir / "1Cv8.1CD").write_bytes(b"dummy")

    captured_conn_strings: list[str] = []

    def mock_factory(conn_str: str) -> Any:
        captured_conn_strings.append(conn_str)
        return object()

    set_test_connector_factory(mock_factory)

    secret_pass = "ENVIRONMENT_SECRET_PASSWORD_123"
    monkeypatch.setenv("ONE_PASSWORD", secret_pass)

    out_file = tmp_path / "result.json"

    # Verify parser has NO --password argument
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["check-one", "--db-path", str(base_dir), "--user", "ro_user", "--password", "secret"])

    # Valid execution
    args = parser.parse_args(["check-one", "--db-path", str(base_dir), "--user", "ro_user", "--output-file", str(out_file)])
    rc = cmd_check_one(args)
    assert rc == 0

    # Verify password was passed to connection string
    assert len(captured_conn_strings) == 1
    assert f'Pwd="{secret_pass}";' in captured_conn_strings[0]

    # Verify stdout JSON
    stdout = capsys.readouterr().out.strip()
    data = json.loads(stdout)
    assert data == {"code": "ok"}
    assert secret_pass not in stdout

    # Verify output file
    file_data = json.loads(out_file.read_text(encoding="utf-8").strip())
    assert file_data == {"code": "ok"}
    assert secret_pass not in out_file.read_text(encoding="utf-8")


def test_cli_check_one_takes_password_from_stdin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    (base_dir / "1Cv8.1CD").write_bytes(b"dummy")

    captured_conn_strings: list[str] = []

    def mock_factory(conn_str: str) -> Any:
        captured_conn_strings.append(conn_str)
        return object()

    set_test_connector_factory(mock_factory)

    stdin_pass = "STDIN_SECRET_PASSWORD_456"
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin_pass + "\n"))
    monkeypatch.delenv("ONE_PASSWORD", raising=False)

    parser = build_parser()
    args = parser.parse_args(["check-one", "--db-path", str(base_dir), "--user", "ro_user", "--password-stdin"])
    rc = cmd_check_one(args)
    assert rc == 0

    assert len(captured_conn_strings) == 1
    assert f'Pwd="{stdin_pass}";' in captured_conn_strings[0]
    stdout = capsys.readouterr().out.strip()
    assert json.loads(stdout) == {"code": "ok"}
    assert stdin_pass not in stdout


def test_sta_thread_initialization_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Item 1: pythoncom.CoInitialize called before connector and CoUninitialize in finally."""
    base_dir = tmp_path / "valid_base"
    base_dir.mkdir()
    (base_dir / "1Cv8.1CD").write_bytes(b"dummy")

    events: list[str] = []

    mock_pythoncom = types.ModuleType("pythoncom")
    mock_pythoncom.CoInitialize = lambda: events.append("co_init")  # type: ignore[attr-defined]
    mock_pythoncom.CoUninitialize = lambda: events.append("co_uninit")  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pythoncom", mock_pythoncom)

    def mock_factory(conn_str: str) -> Any:
        events.append("connect")
        return object()

    set_test_connector_factory(mock_factory)
    code = check_one_connection(str(base_dir), "user", "pass")
    assert code == "ok"
    assert events == ["co_init", "connect", "co_uninit"]


def test_sta_thread_uninitialization_on_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Item 1: pythoncom.CoUninitialize called even when connector raises an exception."""
    base_dir = tmp_path / "valid_base"
    base_dir.mkdir()
    (base_dir / "1Cv8.1CD").write_bytes(b"dummy")

    events: list[str] = []

    mock_pythoncom = types.ModuleType("pythoncom")
    mock_pythoncom.CoInitialize = lambda: events.append("co_init")  # type: ignore[attr-defined]
    mock_pythoncom.CoUninitialize = lambda: events.append("co_uninit")  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pythoncom", mock_pythoncom)

    def mock_factory(conn_str: str) -> Any:
        events.append("connect_error")
        raise RuntimeError("Ошибка аутентификации")

    set_test_connector_factory(mock_factory)
    code = check_one_connection(str(base_dir), "user", "pass")
    assert code == "auth_failed"
    assert events == ["co_init", "connect_error", "co_uninit"]


def test_check_one_timeout_returns_promptly(tmp_path: Path) -> None:
    """Item 2: check_one_connection returns 'timeout' without waiting for hanging worker."""
    base_dir = tmp_path / "valid_base"
    base_dir.mkdir()
    (base_dir / "1Cv8.1CD").write_bytes(b"dummy")

    def hanging_factory(conn_str: str) -> Any:
        time.sleep(5.0)
        return object()

    set_test_connector_factory(hanging_factory)
    start_time = time.monotonic()
    code = check_one_connection(str(base_dir), "user", "pass", timeout_seconds=0.2)
    elapsed = time.monotonic() - start_time
    assert code == "timeout"
    assert elapsed < 1.0


def test_check_one_subprocess_hung_connector_terminates_promptly(tmp_path: Path) -> None:
    """Item 2: check-one CLI subprocess terminates promptly even when COM connector hangs."""
    base_dir = tmp_path / "valid_base"
    base_dir.mkdir()
    (base_dir / "1Cv8.1CD").write_bytes(b"dummy")
    out_file = tmp_path / "probe_result.json"

    env = os.environ.copy()
    src_dir = str(Path(__file__).resolve().parent.parent / "src")
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{src_dir}:{existing_pp}" if existing_pp else src_dir
    env["_ONE_CHECK_TEST_MOCK"] = "hang"
    env["_ONE_CHECK_TEST_HANG_SECONDS"] = "15.0"
    env["ONE_PASSWORD"] = "test_pwd"

    start_time = time.monotonic()
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "poscenter_loyalty_agent.main",
            "check-one",
            "--db-path",
            str(base_dir),
            "--user",
            "test_user",
            "--timeout",
            "0.3",
            "--output-file",
            str(out_file),
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=5.0,
    )
    elapsed = time.monotonic() - start_time

    assert proc.returncode == 1
    assert elapsed < 3.0, f"Subprocess took too long ({elapsed:.2f}s); expected prompt termination"

    stdout_line = proc.stdout.strip()
    data = json.loads(stdout_line)
    assert data == {"code": "timeout"}

    assert out_file.is_file()
    file_data = json.loads(out_file.read_text(encoding="utf-8").strip())
    assert file_data == {"code": "timeout"}

