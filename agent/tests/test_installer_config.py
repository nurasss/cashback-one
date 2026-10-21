"""Unit tests for installer configuration serialization and ACL hardening using real compiled harnesses."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest

from poscenter_loyalty_agent.config import AgentSettings

ISCC_PATH = r"C:\cb-build\tools\innosetup\ISCC.exe"
PACKAGING_DIR = Path(__file__).parent.parent / "packaging"
HARNESS_SERIALIZER_ISS = PACKAGING_DIR / "harness_serializer.iss"
HARNESS_SERIALIZER_EXE = PACKAGING_DIR / "output" / "harness_serializer.exe"
HARNESS_SCM_ISS = PACKAGING_DIR / "harness_scm.iss"
HARNESS_SCM_EXE = PACKAGING_DIR / "output" / "harness_scm.exe"
HARNESS_ACL_ISS = PACKAGING_DIR / "harness_acl.iss"
HARNESS_ACL_EXE = PACKAGING_DIR / "output" / "harness_acl.exe"


def ensure_harness_built(iss_path: Path, exe_path: Path) -> None:
    """Ensure the specified Inno Setup harness binary is compiled and up-to-date."""
    if not exe_path.exists() or exe_path.stat().st_mtime < iss_path.stat().st_mtime:
        if not os.path.exists(ISCC_PATH):
            pytest.skip(f"ISCC compiler not found at {ISCC_PATH}")
        res = subprocess.run([ISCC_PATH, str(iss_path)], cwd=str(PACKAGING_DIR), capture_output=True, text=True)
        if res.returncode != 0:
            pytest.fail(f"Failed to compile {iss_path}: {res.stderr or res.stdout}")
        assert exe_path.exists(), f"Expected harness binary {exe_path} not found after compilation"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: Any) -> None:
    """Ensure environment variables do not override test .env file settings."""
    monkeypatch.delenv("AGENT_API_KEY", raising=False)
    monkeypatch.delenv("ONE_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("AGENT_ENV", raising=False)
    monkeypatch.delenv("AGENT_CLOUD_BASE_URL", raising=False)
    monkeypatch.delenv("ONE_ADAPTER_MODE", raising=False)
    monkeypatch.delenv("AGENT_POLL_INTERVAL_SECONDS", raising=False)
    monkeypatch.delenv("AGENT_CLAMP_NEGATIVE_BALANCE", raising=False)


def test_pascal_scm_open_sc_manager() -> None:
    """Verify that Pascal OpenSCManager(0, 0, SC_MANAGER_CONNECT) connects with NULL database without error 123."""
    if not os.path.exists(ISCC_PATH):
        pytest.skip(f"ISCC compiler not found at {ISCC_PATH}")
    ensure_harness_built(HARNESS_SCM_ISS, HARNESS_SCM_EXE)

    with tempfile.TemporaryDirectory() as td:
        status_file = Path(td) / "scm_status.txt"
        cmd = [str(HARNESS_SCM_EXE), "/VERYSILENT", f"/STATUSFILE={status_file}"]
        subprocess.run(cmd)

        assert status_file.exists(), "SCM harness status file was not created"
        output = status_file.read_text(encoding="utf-8").strip()
        assert output.startswith("SUCCESS: Handle="), f"SCM harness failed: {output}"


def _verify_exact_dacl(target_path: Path, is_dir: bool = False) -> tuple[bool, str]:
    out = subprocess.run(["icacls", str(target_path)], capture_output=True, encoding="cp866").stdout
    entries: list[str] = []
    for line in out.splitlines():
        line = line.strip()
        if not line or "Successfully processed" in line or "Успешно обработано" in line:
            continue
        if ":(" in line:
            entries.append(line)

    if not entries:
        return False, f"No ACE entries found in icacls output:\n{out}"

    has_system = False
    has_admins = False
    expected_rights = "(OI)(CI)(F)" if is_dir else "(F)"

    for entry in entries:
        if "(I)" in entry:
            return False, f"Inherited ACE found: {entry}"
        is_sys = ("S-1-5-18" in entry) or ("SYSTEM" in entry) or ("СИСТЕМА" in entry)
        is_adm = ("S-1-5-32-544" in entry) or ("Administrators" in entry) or ("Администраторы" in entry)
        if not (is_sys or is_adm):
            return False, f"Foreign ACE found: {entry}"
        if expected_rights not in entry:
            return False, f"Expected {expected_rights} in ACE, got: {entry}"
        if is_sys:
            has_system = True
        if is_adm:
            has_admins = True

    if not (has_system and has_admins):
        return False, f"Missing SYSTEM or Administrators ACE: entries={entries}"
    return True, "DACL is exact"


def test_exact_dacl_hardening() -> None:
    """Test exact DACL hardening using compiled Pascal harness (SetNamedSecurityInfoW).

    Verifies:
    1. Parent directory with broad permissions (Users R/W).
    2. Child directory and existing sensitive file with dummy secret and foreign explicit ACE.
    3. Compiled Pascal harness applies atomic protected DACL without icacls /reset.
    4. Strips all foreign ACEs and disables inheritance (zero window of exposure).
    5. Leaves ONLY SYSTEM and Administrators with Full Control.
    6. Verifies failure closed on non-existent targets.
    """
    if not os.path.exists(ISCC_PATH):
        pytest.skip(f"ISCC compiler not found at {ISCC_PATH}")
    ensure_harness_built(HARNESS_ACL_ISS, HARNESS_ACL_EXE)

    td = tempfile.mkdtemp()
    try:
        # 1. Create simulated broad parent directory (analogous to %ProgramData%\POSCENTER\LoyaltyAgent)
        parent_dir = Path(td) / "broad_parent"
        parent_dir.mkdir(parents=True, exist_ok=True)
        # Grant Users (*S-1-5-32-545) Modify/Write permissions with inheritance
        subprocess.run(["icacls", str(parent_dir), "/grant", "*S-1-5-32-545:(OI)(CI)M"], capture_output=True, check=True)

        # 2. Create child config directory and existing sensitive file with dummy secret
        config_dir = parent_dir / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        secret_file = config_dir / ".env.service"
        dummy_secret = "AGENT_API_KEY='dummy-secret-value-12345'\nONE_CONNECTION_STRING='dummy-conn'\n"
        secret_file.write_text(dummy_secret, encoding="utf-8")

        # 3. Inject foreign explicit ACE on both directory and secret file
        subprocess.run(["icacls", str(config_dir), "/grant", "*S-1-5-32-545:(OI)(CI)F"], capture_output=True, check=True)
        subprocess.run(["icacls", str(secret_file), "/grant", "*S-1-5-32-545:F"], capture_output=True, check=True)

        # 4. Confirm foreign ACEs and inherited permissions are present before hardening
        out_f_before = subprocess.run(["icacls", str(secret_file)], capture_output=True, encoding="cp866").stdout
        out_d_before = subprocess.run(["icacls", str(config_dir)], capture_output=True, encoding="cp866").stdout
        assert "S-1-5-32-545" in out_f_before or "Пользователи" in out_f_before or "Users" in out_f_before
        assert "S-1-5-32-545" in out_d_before or "Пользователи" in out_d_before or "Users" in out_d_before
        assert "(I)" in out_f_before, "Existing secret file must have inherited permissions from broad parent"

        # 5. Apply atomic DACL hardening on existing secret file via real compiled Pascal harness
        status_file = Path(td) / "status_file.txt"
        cmd_file = [str(HARNESS_ACL_EXE), "/VERYSILENT", f"/TARGET={secret_file}", "/ISDIR=0", f"/STATUSFILE={status_file}"]
        subprocess.run(cmd_file)
        assert status_file.exists(), "Pascal ACL harness did not create status file"
        assert status_file.read_text(encoding="utf-8").strip() == "SUCCESS", "Pascal ACL harness failed to harden file"

        # 6. Verify exact DACL on secret file:
        # - NO inherited permissions
        # - NO foreign ACEs
        # - ONLY SYSTEM and Administrators with Full Control (F)
        # - Standard user is denied read access
        ok_f, msg_f = _verify_exact_dacl(secret_file, is_dir=False)
        assert ok_f, f"File DACL verification failed: {msg_f}"
        with pytest.raises(PermissionError):
            secret_file.read_text(encoding="utf-8")

        # 7. Apply atomic DACL hardening on directory via real compiled Pascal harness
        status_dir = Path(td) / "status_dir.txt"
        cmd_dir = [str(HARNESS_ACL_EXE), "/VERYSILENT", f"/TARGET={config_dir}", "/ISDIR=1", f"/STATUSFILE={status_dir}"]
        subprocess.run(cmd_dir)
        assert status_dir.exists(), "Pascal ACL harness did not create status file for dir"
        assert status_dir.read_text(encoding="utf-8").strip() == "SUCCESS", "Pascal ACL harness failed to harden directory"

        # 8. Verify exact DACL on directory:
        # - NO inherited permissions
        # - NO foreign ACEs
        # - ONLY SYSTEM and Administrators with (OI)(CI)(F)
        ok_d, msg_d = _verify_exact_dacl(config_dir, is_dir=True)
        assert ok_d, f"Directory DACL verification failed: {msg_d}"

        # 9. Verify error handling: non-existent target fails gracefully
        status_err = Path(td) / "status_err.txt"
        nonexistent = Path(td) / "nonexistent_target_path.txt"
        cmd_err = [str(HARNESS_ACL_EXE), "/VERYSILENT", f"/TARGET={nonexistent}", "/ISDIR=0", f"/STATUSFILE={status_err}"]
        subprocess.run(cmd_err)
        assert status_err.exists(), "Pascal ACL harness did not create status file for error case"
        assert status_err.read_text(encoding="utf-8").strip() == "FAILED"

    finally:
        # Unlock permissions in reverse hierarchy so current test process can read and clean up
        subprocess.run(["icacls", str(Path(td) / "broad_parent" / "config"), "/grant", "*S-1-5-32-545:(OI)(CI)F"], capture_output=True)
        subprocess.run(["icacls", str(Path(td) / "broad_parent" / "config" / ".env.service"), "/grant", "*S-1-5-32-545:F"], capture_output=True)
        subprocess.run(["icacls", str(Path(td) / "broad_parent"), "/grant", "*S-1-5-32-545:(OI)(CI)F"], capture_output=True)
        # Verify secret content was never corrupted or altered
        restored_file = Path(td) / "broad_parent" / "config" / ".env.service"
        if restored_file.exists():
            assert restored_file.read_text(encoding="utf-8") == dummy_secret
        shutil.rmtree(td, ignore_errors=True)


@pytest.mark.parametrize(
    ("one_path", "one_user", "one_pass"),
    [
        (r"\\server\share\База 1С\Касса №1", 'user "admin" & operator', r'P@ss#1&$2"double"\\slash\!@%'),
        (r"\\192.168.1.50\bases\one", "simple_user", "PlainP@ssword123"),
        (r"C:\Базы 1С\Главная Касса", 'oper"1"', r"p@ss\with\single\slash"),
        ("D:\\Data\\one\\", "admin", "pass"),
        (r"\\?\C:\Very\Deep\\Path", 'user "special"', r"P@$$\\$$"),
    ],
)
def test_pascal_harness_serialization_roundtrip(one_path: str, one_user: str, one_pass: str) -> None:
    """Verify that real Pascal SerializeConfigToFile serializes exact values that roundtrip into AgentSettings."""
    if not os.path.exists(ISCC_PATH):
        pytest.skip(f"ISCC compiler not found at {ISCC_PATH}")
    ensure_harness_built(HARNESS_SERIALIZER_ISS, HARNESS_SERIALIZER_EXE)

    with tempfile.TemporaryDirectory() as td:
        param_file = Path(td) / "input.txt"
        out_file = Path(td) / ".env.service"
        status_file = Path(td) / "status.txt"
        cloud_url = "https://api.cashback-qr.poscenter.kz"
        api_key = "test-api-key-1234567890"

        lines = [
            "Mode=serialize",
            f"OutFile={out_file}",
            f"StatusFile={status_file}",
            f"CloudUrl={cloud_url}",
            f"ApiKey={api_key}",
            f"OnePath={one_path}",
            f"OneUser={one_user}",
            f"OnePass={one_pass}",
        ]
        param_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        cmd = [str(HARNESS_SERIALIZER_EXE), "/VERYSILENT", f"/PARAMFILE={param_file}"]
        subprocess.run(cmd)

        assert status_file.exists(), "Harness did not produce status file"
        status = status_file.read_text(encoding="utf-8").strip()
        assert status == "SUCCESS", f"Harness serialization returned error: {status}"

        # 1. Byte-level UTF-8 validation
        raw_bytes = out_file.read_bytes()
        assert not raw_bytes.startswith(b"\xef\xbb\xbf"), "Output file must be UTF-8 without BOM"
        decoded_text = raw_bytes.decode("utf-8")  # Must decode cleanly as UTF-8

        # 2. Roundtrip loading through AgentSettings
        dummy_mapping = Path(td) / "stage0_mapping.json"
        dummy_mapping.write_text("{}", encoding="utf-8")

        settings = AgentSettings(
            _env_file=str(out_file),
            one_mapping_path=dummy_mapping,
        )

        assert settings.agent_cloud_base_url == cloud_url
        assert settings.agent_api_key == api_key

        # Build expected 1C connection string with doubled quotes
        esc_path = one_path.replace('"', '""')
        esc_user = one_user.replace('"', '""')
        esc_pwd = one_pass.replace('"', '""')
        expected_conn_str = f'File="{esc_path}";Usr="{esc_user}";Pwd="{esc_pwd}";'

        assert settings.one_connection_string == expected_conn_str
        assert one_path in settings.one_connection_string
        assert decoded_text.count("AGENT_ENV='production'") == 1


@pytest.mark.parametrize(
    ("field_name", "field_val", "expected_valid"),
    [
        ("Пароль", "valid_P@ss#1&$2", True),
        ("Пользователь", 'user "admin" & operator', True),
        ("Каталог 1С", r"\\server\share\1C", True),
        ("Пароль", "p@ss${INTRUSION}", False),
        ("Пользователь", "O'Connor", False),
        ("Путь", r"C:\db\nline2", False),
        ("Путь", r"C:\db\rline2", False),
    ],
)
def test_pascal_harness_validation_rejections(field_name: str, field_val: str, expected_valid: bool) -> None:
    """Verify that actual Pascal CheckDisallowedInputMsg rejects ${, single quotes, and newlines."""
    if not os.path.exists(ISCC_PATH):
        pytest.skip(f"ISCC compiler not found at {ISCC_PATH}")
    ensure_harness_built(HARNESS_SERIALIZER_ISS, HARNESS_SERIALIZER_EXE)

    with tempfile.TemporaryDirectory() as td:
        param_file = Path(td) / "val_input.txt"
        status_file = Path(td) / "val_status.txt"

        lines = [
            "Mode=validate",
            f"StatusFile={status_file}",
            f"CheckField={field_name}",
            f"CheckVal={field_val}",
        ]
        param_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        cmd = [str(HARNESS_SERIALIZER_EXE), "/VERYSILENT", f"/PARAMFILE={param_file}"]
        subprocess.run(cmd)

        assert status_file.exists(), "Validation harness did not create status file"
        status = status_file.read_text(encoding="utf-8").strip()
        if expected_valid:
            assert status == "VALID", f"Expected valid input for {field_val}, got {status}"
        else:
            assert status.startswith("INVALID:"), f"Expected invalid rejection for {field_val}, got {status}"


def test_installer_env_missing_required_blocks_production() -> None:
    """Production mode must reject empty API key or missing 1C connection string."""
    with tempfile.TemporaryDirectory() as td:
        env_path = Path(td) / ".env.service"
        content = (
            "AGENT_ENV='production'\n"
            "AGENT_CLOUD_BASE_URL='https://api.cashback-qr.poscenter.kz'\n"
            "AGENT_API_KEY='valid-key-length-greater-16'\n"
            "ONE_ADAPTER_MODE='com'\n"
            "ONE_CONNECTION_STRING=''\n"
        )
        env_path.write_text(content, encoding="utf-8")

        dummy_mapping = Path(td) / "stage0_mapping.json"
        dummy_mapping.write_text("{}", encoding="utf-8")

        with pytest.raises(ValueError, match="ONE_CONNECTION_STRING is required"):
            AgentSettings(
                _env_file=str(env_path),
                one_mapping_path=dummy_mapping,
            )


def test_production_url_https_enforcement() -> None:
    """Production cloud URL must use HTTPS."""
    with tempfile.TemporaryDirectory() as td:
        env_path = Path(td) / ".env.service"
        content = (
            "AGENT_ENV='production'\n"
            "AGENT_CLOUD_BASE_URL='http://insecure.cloud.example.com'\n"
            "AGENT_API_KEY='valid-key-length-greater-16'\n"
            "ONE_ADAPTER_MODE='com'\n"
            "ONE_CONNECTION_STRING='File=\"C:\\1C\";'\n"
        )
        env_path.write_text(content, encoding="utf-8")

        dummy_mapping = Path(td) / "stage0_mapping.json"
        dummy_mapping.write_text("{}", encoding="utf-8")

        with pytest.raises(ValueError, match="AGENT_CLOUD_BASE_URL must use HTTPS in production"):
            AgentSettings(
                _env_file=str(env_path),
                one_mapping_path=dummy_mapping,
            )
