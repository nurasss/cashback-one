"""
POSCENTER ONE Keremet Metadata Inspector (Phase 1, Rework 3 Final).
STRICTLY READ-ONLY: Environment check, configuration validation, and 1C metadata cataloging.
NO SQL/1C record queries. NO customer card data. ZERO secrets leakage.
Supports supervisor subprocess execution with guaranteed child termination on timeout.
"""
from __future__ import annotations

import argparse
import base64
import ctypes
from ctypes import wintypes
import json
import os
import re
import secrets
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# ==============================================================================
# Safe Diagnostic Error Codes (Strict Allowlist)
# ==============================================================================
ERR_OK = "OK"
ERR_PRECHECK_PYTHON_ARCH = "PRECHECK_PYTHON_ARCH_NOT_X86"
ERR_PRECHECK_PYTHON_VER = "PRECHECK_PYTHON_VERSION_TOO_OLD"
ERR_PRECHECK_PYWIN32 = "PRECHECK_PYWIN32_MISSING"
ERR_PRECHECK_CONFIG_NOT_FOUND = "PRECHECK_CONFIG_NOT_FOUND"
ERR_PRECHECK_CONFIG_ACCESS_DENIED = "PRECHECK_CONFIG_ACCESS_DENIED"
ERR_PRECHECK_CONFIG_EMPTY = "PRECHECK_CONFIG_EMPTY"
ERR_PRECHECK_CONFIG_CONFLICT = "PRECHECK_CONFIG_PASSWORD_CONFLICT"
ERR_PRECHECK_DPAPI_FAILED = "PRECHECK_DPAPI_DECRYPTION_FAILED"
ERR_PRECHECK_OPERATOR_CONFIRMATION_REQUIRED = "PRECHECK_OPERATOR_CONFIRMATION_REQUIRED"
ERR_PRECHECK_WRONG_BUSINESS_TARGET = "PRECHECK_WRONG_BUSINESS_TARGET"
ERR_PRECHECK_TEST_TARGET_BLOCKED = "PRECHECK_TEST_TARGET_BLOCKED"
ERR_COM_NOT_REGISTERED = "COM_NOT_REGISTERED"
ERR_COM_AUTH_FAILED = "COM_AUTH_FAILED"
ERR_COM_DB_NOT_FOUND = "COM_DB_NOT_FOUND"
ERR_COM_DB_LOCKED = "COM_DB_LOCKED"
ERR_COM_CONNECTION_FAILED = "COM_CONNECTION_FAILED"
ERR_METADATA_TIMEOUT = "METADATA_TIMEOUT"
ERR_METADATA_ACCESS_DENIED = "METADATA_ACCESS_DENIED"
ERR_METADATA_READ_ERROR = "METADATA_READ_ERROR"
ERR_OUTPUT_DIR_CREATE_FAILED = "OUTPUT_DIR_CREATE_FAILED"
ERR_REPORT_WRITE_FAILED = "REPORT_WRITE_FAILED"
ERR_UNEXPECTED = "UNEXPECTED_ERROR"

# Application DPAPI entropy for POSCENTER Loyalty Agent
DPAPI_ENTROPY: bytes = b"POSCENTER_LOYALTY_AGENT_DPAPI_SALT_v1"
DEFAULT_CONFIG_PATH = Path(r"C:\ProgramData\POSCENTER\LoyaltyAgent\config\.env.service")
DEFAULT_OUTPUT_BASE = Path(r"C:\cashback-inspection\keremet-turnover")
DEFAULT_TIMEOUT_SECONDS = 25.0

# Mock hooks for unit tests
_mock_com_factory: Any = None
_mock_dpapi_backend: Any = None
_test_worker_script_path: Path | None = None


def set_test_hooks(
    com_factory: Any = None,
    dpapi_backend: Any = None,
    worker_script_override: Path | None = None,
) -> None:
    global _mock_com_factory, _mock_dpapi_backend, _test_worker_script_path
    _mock_com_factory = com_factory
    _mock_dpapi_backend = dpapi_backend
    _test_worker_script_path = worker_script_override


# ==============================================================================
# Helper: Parse .env.service matching Inno Setup / python-dotenv unquoting
# ==============================================================================
def unquote_dotenv_value(val: str) -> str:
    """Unquote and unescape a dotenv value matching FormatDotEnvValue/UnquoteDotEnvValue in Inno Setup.

    In Inno Setup (config_serializer.iss) and python-dotenv, quoted values escape literal backslashes as \\\\.
    Unwrapping outer quotes and replacing \\\\ with \\ restores the original unescaped string.
    Does NOT use unicode_escape (preserving Cyrillic characters).
    """
    v = val.strip()
    if (len(v) >= 2 and v.startswith("'") and v.endswith("'")) or \
       (len(v) >= 2 and v.startswith('"') and v.endswith('"')):
        v = v[1:-1]
        v = v.replace(r"\\", "\\")
    return v


def parse_env_service_file(path: Path) -> dict[str, str]:
    """Parse .env.service strictly from disk without reading os.environ."""
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    content = path.read_text(encoding="utf-8")
    cfg: dict[str, str] = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            k = k.strip()
            cfg[k] = unquote_dotenv_value(v)
    return cfg


# ==============================================================================
# Helper: 1C Connection String Password Injection (matches agent config.py)
# ==============================================================================
def inject_1c_password(conn_str: str, password: str) -> str:
    """Inject or replace Pwd in 1C connection string with quote escaping."""
    esc_pwd = password.replace('"', '""')
    pwd_clause = f'Pwd="{esc_pwd}";'
    if re.search(r'(?i)Pwd\s*=', conn_str):
        return re.sub(r'(?i)Pwd\s*=\s*("([^"]*)"|\'([^\']*)\'|[^;]*)(;?)', pwd_clause, conn_str)
    clean = conn_str.strip()
    if clean and not clean.endswith(';'):
        clean += ';'
    return clean + pwd_clause


def extract_1c_password(conn_str: str) -> str | None:
    """Extract Pwd value from connection string if present."""
    m = re.search(r'(?i)Pwd\s*=\s*("([^"]*)"|\'([^\']*)\'|([^;]*))', conn_str)
    if m:
        return m.group(2) if m.group(2) is not None else (m.group(3) if m.group(3) is not None else m.group(4))
    return None


# ==============================================================================
# DPAPI Unprotect (in-memory)
# ==============================================================================
class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def unprotect_dpapi_secret(b64_cipher: str, entropy: bytes = DPAPI_ENTROPY) -> str:
    """Decrypt a DPAPI string in memory using LocalMachine scope. Zero secrets logged."""
    if _mock_dpapi_backend is not None:
        return _mock_dpapi_backend.unprotect(b64_cipher)

    if sys.platform != "win32":
        raise RuntimeError("DPAPI is only supported on Windows")

    clean = b64_cipher.strip()
    if not clean:
        return ""

    try:
        raw_cipher = base64.b64decode(clean, validate=True)
    except Exception as exc:
        raise ValueError("DPAPI_DECODE_ERROR") from exc

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    in_blob = DATA_BLOB()
    in_blob.cbData = len(raw_cipher)
    in_buf = (ctypes.c_byte * len(raw_cipher)).from_buffer_copy(raw_cipher)
    in_blob.pbData = ctypes.cast(in_buf, ctypes.POINTER(ctypes.c_byte))

    ent_blob = DATA_BLOB()
    ent_blob.cbData = len(entropy)
    ent_buf = (ctypes.c_byte * len(entropy)).from_buffer_copy(entropy)
    ent_blob.pbData = ctypes.cast(ent_buf, ctypes.POINTER(ctypes.c_byte))

    out_blob = DATA_BLOB()
    CRYPTPROTECT_UI_FORBIDDEN = 0x00000001

    res = crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        ctypes.byref(ent_blob),
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out_blob),
    )
    if not res:
        raise RuntimeError("CRYPT_UNPROTECT_FAILED")

    try:
        out_bytes = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        return out_bytes.decode("utf-8")
    finally:
        kernel32.LocalFree(out_blob.pbData)


# ==============================================================================
# Stage 1: Prerequisites & Configuration Validation
# ==============================================================================
def verify_prerequisites(
    config_path: Path,
    expected_business: str | None,
    confirm_operator: bool = False,
    skip_arch_check: bool = False,
) -> tuple[bool, str, dict[str, str]]:
    """Verify runtime environment, architecture, modules, config readability, and target business."""
    if not expected_business or expected_business.strip().lower() != "keremet":
        return False, ERR_PRECHECK_WRONG_BUSINESS_TARGET, {}

    if not confirm_operator:
        return False, ERR_PRECHECK_OPERATOR_CONFIRMATION_REQUIRED, {}

    if not skip_arch_check and sys.platform == "win32" and sys.maxsize > 2**32:
        return False, ERR_PRECHECK_PYTHON_ARCH, {}

    if sys.version_info < (3, 10):
        return False, ERR_PRECHECK_PYTHON_VER, {}

    if sys.platform == "win32" and not _mock_com_factory:
        try:
            import pythoncom  # type: ignore[import-untyped]
            import win32com.client  # type: ignore[import-untyped]
        except ImportError:
            return False, ERR_PRECHECK_PYWIN32, {}

    if not config_path.exists():
        return False, ERR_PRECHECK_CONFIG_NOT_FOUND, {}

    try:
        cfg = parse_env_service_file(config_path)
    except PermissionError:
        return False, ERR_PRECHECK_CONFIG_ACCESS_DENIED, {}
    except Exception:
        return False, ERR_PRECHECK_CONFIG_ACCESS_DENIED, {}

    if not cfg:
        return False, ERR_PRECHECK_CONFIG_EMPTY, {}

    # Target business local barrier: verify connection does not target known test infobase
    conn_str = cfg.get("ONE_CONNECTION_STRING", "")
    db_path = cfg.get("ONE_DB_PATH", "")
    raw_target = f"{conn_str};{db_path}".lower()

    if "c:\\1c_data\\int" in raw_target or "/1c_data/int" in raw_target or "\\int\\" in raw_target:
        return False, ERR_PRECHECK_TEST_TARGET_BLOCKED, {}

    return True, ERR_OK, cfg


# ==============================================================================
# Stage 2: Safe Connection Builder (with DPAPI injection & conflict checks)
# ==============================================================================
def build_connection_string(config: dict[str, str]) -> tuple[str, str]:
    """Build sanitized connection string in memory with proper password injection.

    Returns (connection_string, error_code).
    """
    raw_conn = config.get("ONE_CONNECTION_STRING", "")
    plain_pwd = config.get("ONE_PASSWORD", "").strip()
    dpapi_pwd = config.get("ONE_PASSWORD_DPAPI", "").strip()

    conn_pwd = extract_1c_password(raw_conn)
    has_conn_pwd = conn_pwd is not None and len(conn_pwd) > 0
    has_plain_pwd = bool(plain_pwd)
    has_dpapi_pwd = bool(dpapi_pwd)

    # Conflict checks (matching agent config.py)
    if has_dpapi_pwd and (has_plain_pwd or has_conn_pwd):
        return "", ERR_PRECHECK_CONFIG_CONFLICT
    if has_plain_pwd and has_conn_pwd and plain_pwd != conn_pwd:
        return "", ERR_PRECHECK_CONFIG_CONFLICT

    if has_dpapi_pwd:
        try:
            resolved_pwd = unprotect_dpapi_secret(dpapi_pwd)
        except Exception:
            return "", ERR_PRECHECK_DPAPI_FAILED
    elif has_plain_pwd:
        resolved_pwd = plain_pwd
    elif has_conn_pwd:
        resolved_pwd = conn_pwd
    else:
        resolved_pwd = ""

    # Build base connection string
    if raw_conn:
        base_conn = raw_conn
    else:
        db_path = config.get("ONE_DB_PATH", "")
        usr = config.get("ONE_USER", "")
        if db_path:
            base_conn = f'File="{db_path}";Usr="{usr}";'
        else:
            srvr = config.get("ONE_SERVER", "")
            ref = config.get("ONE_REF", "")
            base_conn = f'Srvr="{srvr}";Ref="{ref}";Usr="{usr}";'

    final_conn = inject_1c_password(base_conn, resolved_pwd)
    return final_conn, ERR_OK


def classify_com_error(exc: Exception) -> str:
    """Map raw COM exception to safe allowlist code without leaking strings."""
    s = str(exc).lower()
    if any(w in s for w in ("80040154", "800401f3", "comconnector", "not registered", "не зарегистрирован")):
        return ERR_COM_NOT_REGISTERED
    if any(w in s for w in ("пароль", "password", "идентификация", "auth", "access denied", "неверные имя")):
        return ERR_COM_AUTH_FAILED
    if any(w in s for w in ("не найдена", "not found", "1cv8.1cd", "файл не найден")):
        return ERR_COM_DB_NOT_FOUND
    if any(w in s for w in ("заблокирована", "locked", "exclusive", "монопольн")):
        return ERR_COM_DB_LOCKED
    return ERR_COM_CONNECTION_FAILED


def establish_com_connection(conn_str: str) -> tuple[Any, str]:
    """Connect to 1C COMConnector in STA apartment. Returns (conn, error_code)."""
    if _mock_com_factory is not None:
        try:
            conn = _mock_com_factory(conn_str)
            return conn, ERR_OK
        except Exception as exc:
            return None, classify_com_error(exc)

    try:
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        connector = win32com.client.Dispatch("V83.COMConnector")
        conn = connector.Connect(conn_str)
        return conn, ERR_OK
    except Exception as exc:
        return None, classify_com_error(exc)


# ==============================================================================
# Stage 3: Metadata Cataloging (No Record Queries)
# ==============================================================================
RELEVANT_KEYWORDS = re.compile(r"(?i)(бонус|карт|лояльн|скидк|покупател|клиент|продаж|чек|возврат|выручк)")
COLLECTION_LIMIT = 200
ATTRIBUTE_LIMIT = 50


def inspect_collection_safe(collection_obj: Any, category_name: str) -> tuple[dict[str, Any], str]:
    """Enumerate metadata items in a collection by iterating count/items.

    Returns (dict_of_items, error_code). Halts on access/COM errors.
    """
    items_out: dict[str, Any] = {}
    try:
        total_count = int(collection_obj.Количество())
    except Exception as exc:
        s = str(exc).lower()
        if "access" in s or "permission" in s or "доступ" in s:
            return {}, ERR_METADATA_ACCESS_DENIED
        return {}, ERR_METADATA_READ_ERROR

    scan_limit = min(total_count, COLLECTION_LIMIT)

    for i in range(scan_limit):
        try:
            item = collection_obj[i]
            item_name = str(item.Имя)
        except Exception as exc:
            s = str(exc).lower()
            if "access" in s or "permission" in s or "доступ" in s:
                return {}, ERR_METADATA_ACCESS_DENIED
            return {}, ERR_METADATA_READ_ERROR

        is_relevant = bool(RELEVANT_KEYWORDS.search(item_name))
        entry: dict[str, Any] = {
            "status": "EXISTS",
            "is_relevant": is_relevant,
        }

        # If item is relevant to cards/sales/loyalty, inspect its structure
        if is_relevant:
            try:
                if hasattr(item, "Реквизиты"):
                    attr_cnt = int(item.Реквизиты.Количество())
                    entry["attributes"] = [str(item.Реквизиты[j].Имя) for j in range(min(attr_cnt, ATTRIBUTE_LIMIT))]
                if hasattr(item, "Измерения"):
                    dim_cnt = int(item.Измерения.Количество())
                    entry["dimensions"] = [str(item.Измерения[j].Имя) for j in range(min(dim_cnt, ATTRIBUTE_LIMIT))]
                if hasattr(item, "Ресурсы"):
                    res_cnt = int(item.Ресурсы.Количество())
                    entry["resources"] = [str(item.Ресурсы[j].Имя) for j in range(min(res_cnt, ATTRIBUTE_LIMIT))]
            except Exception as exc:
                s = str(exc).lower()
                if "access" in s or "permission" in s:
                    return {}, ERR_METADATA_ACCESS_DENIED
                return {}, ERR_METADATA_READ_ERROR

        items_out[item_name] = entry

    return {
        "total_in_configuration": total_count,
        "scanned_count": scan_limit,
        "is_truncated": total_count > scan_limit,
        "items": items_out,
    }, ERR_OK


def inspect_metadata_phase1(conn: Any) -> tuple[dict[str, Any], str]:
    """Catalog metadata collections without running queries.

    Halts immediately on unexpected or access errors.
    """
    try:
        md = conn.Метаданные
    except Exception:
        return {}, ERR_METADATA_READ_ERROR

    collections = [
        ("catalogs", md.Справочники),
        ("accumulation_registers", md.РегистрыНакопления),
        ("information_registers", md.РегистрыСведений),
        ("documents", md.Документы),
    ]

    out: dict[str, Any] = {}
    for col_key, col_obj in collections:
        col_res, err = inspect_collection_safe(col_obj, col_key)
        if err != ERR_OK:
            return {}, err
        out[col_key] = col_res

    return out, ERR_OK


# ==============================================================================
# Worker Execution (Worker Process / In-Process Runner)
# ==============================================================================
def execute_worker(
    config_path: Path,
    run_dir: Path,
    expected_business: str | None,
    confirm_operator: bool = False,
    skip_arch: bool = False,
) -> int:
    """Run worker execution: prerequisites -> connect -> inspect -> save report."""
    start_t = time.monotonic()

    # 1. Prerequisites
    ok, err_code, cfg = verify_prerequisites(config_path, expected_business, confirm_operator, skip_arch)
    if not ok:
        saved = _save_report(run_dir, "FAILED", "STAGE_PREREQUISITES", err_code, start_t)
        if not saved:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] STOP: Failed to write report: {ERR_REPORT_WRITE_FAILED}", file=sys.stderr)
        return 1

    # 2. Build Connection String
    conn_str, build_err = build_connection_string(cfg)
    if build_err != ERR_OK:
        saved = _save_report(run_dir, "FAILED", "STAGE_CONFIG_BUILD", build_err, start_t)
        if not saved:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] STOP: Failed to write report: {ERR_REPORT_WRITE_FAILED}", file=sys.stderr)
        return 1

    # 3. Connect
    conn, conn_err = establish_com_connection(conn_str)
    if conn_err != ERR_OK:
        saved = _save_report(run_dir, "FAILED", "STAGE_COM_CONNECT", conn_err, start_t)
        if not saved:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] STOP: Failed to write report: {ERR_REPORT_WRITE_FAILED}", file=sys.stderr)
        return 1

    # 4. Inspect Metadata
    try:
        meta, meta_err = inspect_metadata_phase1(conn)
        if meta_err != ERR_OK:
            saved = _save_report(run_dir, "FAILED", "STAGE_METADATA_INSPECTION", meta_err, start_t)
            if not saved:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] STOP: Failed to write report: {ERR_REPORT_WRITE_FAILED}", file=sys.stderr)
            return 3

        saved = _save_report(run_dir, "SUCCESS", "COMPLETE", ERR_OK, start_t, metadata=meta)
        if not saved:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] STOP: Failed to write report: {ERR_REPORT_WRITE_FAILED}", file=sys.stderr)
            return 1
        return 0
    finally:
        if conn is not None:
            try:
                del conn
            except Exception:
                pass
        if sys.platform == "win32" and not _mock_com_factory:
            try:
                import pythoncom

                pythoncom.CoUninitialize()
            except Exception:
                pass


def _save_report(
    run_dir: Path,
    status: str,
    stage: str,
    error_code: str,
    start_t: float,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Save execution report with exclusive creation and no secrets. Returns True on success."""
    try:
        run_dir.mkdir(parents=True, exist_ok=True)
        rep: dict[str, Any] = {
            "status": status,
            "stage": stage,
            "error_code": error_code,
            "duration_ms": round((time.monotonic() - start_t) * 1000, 2),
            "timestamp": datetime.now().isoformat(),
        }
        if metadata:
            rep["metadata"] = metadata

        (run_dir / "metadata_report.json").write_text(
            json.dumps(rep, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        md_lines = [
            f"# Отчёт инспекции метаданных Keremet (Фаза 1: {status})",
            "",
            f"- **Статус:** `{status}`",
            f"- **Стадия:** `{stage}`",
            f"- **Код результата:** `{error_code}`",
            f"- **Время выполнения:** {rep['duration_ms']} мс",
            f"- **Дата:** {rep['timestamp']}",
        ]
        if metadata:
            md_lines.extend([
                "",
                "## Каталогизированные метаданные",
                "```json",
                json.dumps(metadata, indent=2, ensure_ascii=False),
                "```",
            ])
        (run_dir / "metadata_report.md").write_text("\n".join(md_lines), encoding="utf-8")
        return True
    except Exception:
        return False


# ==============================================================================
# Parent Supervisor with True Process Termination on Timeout
# ==============================================================================
def run_supervisor(
    config_path: Path = DEFAULT_CONFIG_PATH,
    output_base: Path = DEFAULT_OUTPUT_BASE,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    business_slug: str | None = None,
    confirm_operator: bool = False,
) -> int:
    """Supervisor runs worker in a subprocess, terminating it cleanly on timeout."""
    start_t = time.monotonic()
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    token = secrets.token_hex(4)
    run_dir = output_base / f"run_{timestamp_str}_{token}"

    try:
        run_dir.mkdir(parents=True, exist_ok=False)
    except Exception:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] STOP: Failed to create output dir: {ERR_OUTPUT_DIR_CREATE_FAILED}", file=sys.stderr)
        return 1

    worker_script = _test_worker_script_path or Path(__file__).resolve()
    cmd = [
        sys.executable,
        str(worker_script),
        "--worker-mode",
        "--config-path", str(config_path),
        "--run-dir", str(run_dir),
    ]
    if business_slug:
        cmd.extend(["--business-slug", business_slug])
    if confirm_operator:
        cmd.append("--confirm-target-operator")

    print(f"[{datetime.now().strftime('%H:%M:%S')}] === START: Keremet Metadata Inspection Phase 1 Supervisor ===")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Output directory: {run_dir}")

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        stdout, stderr = proc.communicate(timeout=timeout_seconds)
        ret_code = proc.returncode
        if stdout:
            print(stdout.strip())
        if stderr:
            print(stderr.strip(), file=sys.stderr)

        # Ensure report file was actually created when worker exited with 0
        if ret_code == 0 and not (run_dir / "metadata_report.json").exists():
            print(f"[{datetime.now().strftime('%H:%M:%S')}] STOP: Worker returned 0 but report file was not written: {ERR_REPORT_WRITE_FAILED}", file=sys.stderr)
            return 1

        return ret_code
    except subprocess.TimeoutExpired:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] STOP: Worker timed out after {timeout_seconds}s. Terminating child process...")
        proc.terminate()
        try:
            proc.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=1.0)

        saved = _save_report(run_dir, "FAILED", "STAGE_SUPERVISOR_TIMEOUT", ERR_METADATA_TIMEOUT, start_t)
        if not saved:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] STOP: Failed to write timeout report: {ERR_REPORT_WRITE_FAILED}", file=sys.stderr)
        return 2


# ==============================================================================
# CLI Entrypoint
# ==============================================================================
def main() -> None:
    parser = argparse.ArgumentParser(description="Keremet 1C Metadata Inspector (Phase 1)")
    parser.add_argument("--worker-mode", action="store_true", help="Internal flag: run in worker mode")
    parser.add_argument("--config-path", type=Path, default=DEFAULT_CONFIG_PATH, help="Path to .env.service")
    parser.add_argument("--run-dir", type=Path, default=None, help="Directory for report output")
    parser.add_argument("--output-base", type=Path, default=DEFAULT_OUTPUT_BASE, help="Base output directory")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS, help="Timeout in seconds")
    parser.add_argument("--business-slug", type=str, required=False, default=None, help="Target business identifier (must be 'keremet')")
    parser.add_argument("--confirm-target-operator", action="store_true", help="Affirmation by local operator confirming target Keremet infobase")
    args = parser.parse_args()

    if args.worker_mode:
        run_dir = args.run_dir or (args.output_base / f"worker_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        code = execute_worker(
            args.config_path,
            run_dir,
            args.business_slug,
            confirm_operator=args.confirm_target_operator,
        )
        sys.exit(code)
    else:
        code = run_supervisor(
            args.config_path,
            args.output_base,
            args.timeout,
            business_slug=args.business_slug,
            confirm_operator=args.confirm_target_operator,
        )
        sys.exit(code)


if __name__ == "__main__":
    main()
