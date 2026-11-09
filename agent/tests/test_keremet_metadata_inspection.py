"""
Comprehensive isolated test suite for Keremet Metadata Inspector (Phase 1, Rework 3 Final).
Covers:
1. Inno Setup / python-dotenv roundtrip unquoting (UNC, local file path, Cyrillic, backslashes).
2. Report saving failure prevents false 0 returncode (returns non-zero on write error).
3. Real run_supervisor execution: child worker process is genuinely terminated on timeout.
4. Real run_supervisor exclusive directory generation without collisions.
5. Operator confirmation barrier (required business slug, operator confirmation flag, blocking test int infobase).
6. DPAPI password injection into connection string with quote escaping.
7. Password conflict detection (plaintext + DPAPI).
8. Metadata traversal halting on read errors (does not mask as NOT_FOUND).
9. Zero secrets leakage across all output channels.
"""
from __future__ import annotations

import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

# Add docs/tools/keremet-inspection to sys.path
INSPECTOR_DIR = Path(__file__).resolve().parents[2] / "docs" / "tools" / "keremet-inspection"
sys.path.insert(0, str(INSPECTOR_DIR))

import inspect_metadata as im  # noqa: E402


class MockMetadataCollection:
    def __init__(self, items: list[Any], throw_on_access: Exception | None = None):
        self._items = items
        self._throw = throw_on_access
        self.Количество = MagicMock(side_effect=self._get_count)

    def _get_count(self):
        if self._throw:
            raise self._throw
        return len(self._items)

    def __getitem__(self, idx: int):
        if self._throw:
            raise self._throw
        return self._items[idx]


class Mock1CMetadataItem:
    def __init__(self, name: str, attributes: list[str] | None = None, dimensions: list[str] | None = None, resources: list[str] | None = None):
        self.Имя = name
        self._attrs = [MagicMock(Имя=a) for a in (attributes or [])]
        self._dims = [MagicMock(Имя=d) for d in (dimensions or [])]
        self._res = [MagicMock(Имя=r) for r in (resources or [])]

        if attributes is not None:
            self.Реквизиты = MagicMock()
            self.Реквизиты.Количество = MagicMock(return_value=len(self._attrs))
            self.Реквизиты.__getitem__ = lambda s, i: self._attrs[i]

        if dimensions is not None:
            self.Измерения = MagicMock()
            self.Измерения.Количество = MagicMock(return_value=len(self._dims))
            self.Измерения.__getitem__ = lambda s, i: self._dims[i]

        if resources is not None:
            self.Ресурсы = MagicMock()
            self.Ресурсы.Количество = MagicMock(return_value=len(self._res))
            self.Ресурсы.__getitem__ = lambda s, i: self._res[i]


@pytest.fixture(autouse=True)
def reset_hooks():
    im.set_test_hooks(None, None, None)
    yield
    im.set_test_hooks(None, None, None)


# ==============================================================================
# 1. Inno Setup / python-dotenv Roundtrip Unquoting Tests
# ==============================================================================
def format_dotenv_inno_setup_style(s: str) -> str:
    """Format matching FormatDotEnvValue in agent/packaging/config_serializer.iss:86-96."""
    escaped = s.replace("\\", "\\\\")
    return f"'{escaped}'"


@pytest.mark.parametrize(
    "original_val",
    [
        'File="C:\\1C_Data\\keremet";Usr="loyalty_ro";',
        'Srvr="\\\\server\\share\\baza";Ref="keremet";',
        'File="C:\\1C_Данные\\Керемет_Супермаркет";Usr="пользователь_ro";',
        'File="D:\\Bases\\Trade";Usr="admin";Pwd="p\\"w\'123";',
    ],
)
def test_dotenv_roundtrip_matches_inno_setup(tmp_path: Path, original_val: str):
    # Simulate Inno Setup writing .env.service
    serialized_line = f"ONE_CONNECTION_STRING={format_dotenv_inno_setup_style(original_val)}\n"
    cfg_file = tmp_path / ".env.service"
    cfg_file.write_text(serialized_line, encoding="utf-8")

    parsed = im.parse_env_service_file(cfg_file)
    # Crucial assertion: unquoted value MUST strictly equal original unescaped value
    assert parsed["ONE_CONNECTION_STRING"] == original_val


# ==============================================================================
# 2. Failure to Save Report Prevents False 0 Exit Code
# ==============================================================================
def test_save_report_failure_returns_non_zero_code(tmp_path: Path):
    # Create a regular file where run_dir is expected, causing run_dir.mkdir to fail
    blocked_file = tmp_path / "blocked_file"
    blocked_file.write_text("i_am_a_file")

    cfg_file = tmp_path / ".env.service"
    cfg_file.write_text('ONE_CONNECTION_STRING="File=C:\\keremet;Usr=ro;"\n')

    class MockDPAPI:
        def unprotect(self, b): return ""
    im.set_test_hooks(com_factory=lambda c: MagicMock(), dpapi_backend=MockDPAPI())

    ret = im.execute_worker(
        cfg_file,
        run_dir=blocked_file,  # cannot create directory inside a file
        expected_business="keremet",
        confirm_operator=True,
        skip_arch=True,
    )
    # Must NOT return 0!
    assert ret != 0


# ==============================================================================
# 3. Real run_supervisor Call with True Subprocess Termination on Timeout
# ==============================================================================
def test_real_run_supervisor_kills_child_worker_on_timeout(tmp_path: Path):
    pid_file = tmp_path / "child_worker.pid"

    # Helper script executed by supervisor as worker
    helper_script = tmp_path / "mock_worker.py"
    helper_script.write_text(
        "import os, sys, time\n"
        f"with open(r'{pid_file}', 'w') as f:\n"
        "    f.write(str(os.getpid()))\n"
        "time.sleep(30.0)\n"
        "sys.exit(0)\n"
    )

    im.set_test_hooks(worker_script_override=helper_script)

    out_base = tmp_path / "supervisor_out"
    out_base.mkdir()

    t0 = time.monotonic()
    # Call the REAL run_supervisor function
    exit_code = im.run_supervisor(
        config_path=tmp_path / ".env.service",
        output_base=out_base,
        timeout_seconds=0.4,
        business_slug="keremet",
        confirm_operator=True,
    )
    duration = time.monotonic() - t0

    assert exit_code == 2
    assert duration < 3.0

    # Read PID of child process and verify it is genuinely terminated
    assert pid_file.exists()
    child_pid = int(pid_file.read_text().strip())

    # On POSIX / Windows, check child is no longer running
    time.sleep(0.1)
    is_alive = True
    try:
        os.kill(child_pid, 0)
    except OSError:
        is_alive = False

    assert not is_alive, f"Child worker process {child_pid} is still alive!"

    # Verify failure report exists
    run_dirs = list(out_base.glob("run_*"))
    assert len(run_dirs) == 1
    rep = json.loads((run_dirs[0] / "metadata_report.json").read_text(encoding="utf-8"))
    assert rep["status"] == "FAILED"
    assert rep["error_code"] == im.ERR_METADATA_TIMEOUT


def test_real_run_supervisor_exclusive_directory_creation(tmp_path: Path):
    helper_script = tmp_path / "fast_worker.py"
    helper_script.write_text(
        "import sys, json, os, time\n"
        "from pathlib import Path\n"
        "run_dir = Path(sys.argv[sys.argv.index('--run-dir') + 1])\n"
        "run_dir.mkdir(parents=True, exist_ok=True)\n"
        "(run_dir / 'metadata_report.json').write_text(json.dumps({'status': 'SUCCESS', 'error_code': 'OK'}))\n"
        "sys.exit(0)\n"
    )

    im.set_test_hooks(worker_script_override=helper_script)

    out_base = tmp_path / "exclusive_out"
    out_base.mkdir()

    # Call real run_supervisor twice
    c1 = im.run_supervisor(tmp_path / ".env", out_base, 5.0, "keremet", True)
    c2 = im.run_supervisor(tmp_path / ".env", out_base, 5.0, "keremet", True)

    assert c1 == 0
    assert c2 == 0

    run_dirs = sorted(out_base.glob("run_*"))
    assert len(run_dirs) == 2
    assert run_dirs[0] != run_dirs[1]


# ==============================================================================
# 4. Operator Confirmation Barrier Tests
# ==============================================================================
def test_operator_confirmation_barrier(tmp_path: Path):
    cfg_file = tmp_path / ".env.service"
    cfg_file.write_text('ONE_CONNECTION_STRING="File=C:\\keremet;Usr=ro;"\n')

    # Case A: operator confirmation flag missing
    ok, err, _ = im.verify_prerequisites(cfg_file, expected_business="keremet", confirm_operator=False, skip_arch_check=True)
    assert not ok
    assert err == im.ERR_PRECHECK_OPERATOR_CONFIRMATION_REQUIRED

    # Case B: business slug missing or wrong
    ok, err, _ = im.verify_prerequisites(cfg_file, expected_business=None, confirm_operator=True, skip_arch_check=True)
    assert not ok
    assert err == im.ERR_PRECHECK_WRONG_BUSINESS_TARGET

    ok, err, _ = im.verify_prerequisites(cfg_file, expected_business="test", confirm_operator=True, skip_arch_check=True)
    assert not ok
    assert err == im.ERR_PRECHECK_WRONG_BUSINESS_TARGET

    # Case C: points to test int database -> blocked
    test_cfg = tmp_path / "test.env.service"
    test_cfg.write_text('ONE_CONNECTION_STRING="File=C:\\1C_data\\int;Usr=ro;"\n')
    ok, err, _ = im.verify_prerequisites(test_cfg, expected_business="keremet", confirm_operator=True, skip_arch_check=True)
    assert not ok
    assert err == im.ERR_PRECHECK_TEST_TARGET_BLOCKED

    # Case D: proper Keremet target with confirmation
    ok, err, _ = im.verify_prerequisites(cfg_file, expected_business="keremet", confirm_operator=True, skip_arch_check=True)
    assert ok
    assert err == im.ERR_OK


# ==============================================================================
# 5. DPAPI Password Injection & Conflict Tests
# ==============================================================================
def test_dpapi_password_injection():
    received_conn_str: list[str] = []

    def mock_com(conn_str: str):
        received_conn_str.append(conn_str)
        return MagicMock()

    class MockDPAPI:
        def unprotect(self, b): return 'secret"pwd\'99'

    im.set_test_hooks(com_factory=mock_com, dpapi_backend=MockDPAPI())

    cfg = {
        "ONE_CONNECTION_STRING": 'File="C:\\1C_Data\\keremet";Usr="ro";',
        "ONE_PASSWORD_DPAPI": "blob",
    }
    conn_str, err = im.build_connection_string(cfg)
    assert err == im.ERR_OK
    assert 'Pwd="secret""pwd\'99";' in conn_str


def test_password_conflict():
    cfg = {
        "ONE_CONNECTION_STRING": 'File="C:\\keremet";Usr="ro";Pwd="plain";',
        "ONE_PASSWORD_DPAPI": "blob",
    }
    _, err = im.build_connection_string(cfg)
    assert err == im.ERR_PRECHECK_CONFIG_CONFLICT


# ==============================================================================
# 6. Metadata Read Error Halts Traversal
# ==============================================================================
def test_metadata_read_error_halts_traversal():
    first_col = MockMetadataCollection([], throw_on_access=RuntimeError("unexpected COM failure"))
    second_col = MockMetadataCollection([Mock1CMetadataItem("ShouldNeverBeRead")])

    mock_md = MagicMock()
    mock_md.Справочники = first_col
    mock_md.РегистрыНакопления = second_col
    mock_conn = MagicMock(Метаданные=mock_md)

    meta, err = im.inspect_metadata_phase1(mock_conn)
    assert err == im.ERR_METADATA_READ_ERROR
    assert meta == {}
    second_col.Количество.assert_not_called()


# ==============================================================================
# 7. Zero Secrets Leakage on Failure
# ==============================================================================
def test_zero_secrets_leakage_on_failure(tmp_path: Path):
    secret_pass = "P@ssw0rd_With_Quotes_\"'!"
    secret_conn = "File=C:\\KeremetSecret\\1cv8.1cd;Usr=super_admin;"

    class LeakingDPAPI:
        def unprotect(self, b):
            raise RuntimeError(f"DPAPI crash with secret: {secret_pass}")

    im.set_test_hooks(dpapi_backend=LeakingDPAPI())

    cfg_file = tmp_path / ".env.service"
    cfg_file.write_text(f'ONE_CONNECTION_STRING="{secret_conn}"\nONE_PASSWORD_DPAPI="dummy"\n')

    run_dir = tmp_path / "leak_test"
    ret = im.execute_worker(cfg_file, run_dir, "keremet", confirm_operator=True, skip_arch=True)
    assert ret != 0

    report_json = (run_dir / "metadata_report.json").read_text(encoding="utf-8")
    report_md = (run_dir / "metadata_report.md").read_text(encoding="utf-8")

    assert secret_pass not in report_json
    assert secret_conn not in report_json
    assert secret_pass not in report_md
    assert secret_conn not in report_md
