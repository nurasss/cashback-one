"""1C infobase connection verifier (check-one) for POSCENTER Loyalty Agent.

CRITICAL CONSTRAINTS:
1. Strict read-only: does not create, modify, or delete anything in 1C.
2. Does NOT access documents, catalogs, or registers; only verifies connection establishment and disconnects.
3. Zero secrets leakage: passwords and full connection strings are never output or logged.
4. Returns one standardized code: ok, com_not_registered, db_not_found, auth_failed, db_locked, timeout, unknown.
5. STA apartment initialization: pythoncom.CoInitialize() before COM calls and CoUninitialize() in finally.
6. Worker thread is a daemon thread so hung COM calls do not block process termination.
"""

from __future__ import annotations

import logging
import os
import queue
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ConnectorFactory = Callable[[str], Any]
_test_connector_factory: ConnectorFactory | None = None


def set_test_connector_factory(factory: ConnectorFactory | None) -> None:
    """Inject a test connector factory for unit tests."""
    global _test_connector_factory
    _test_connector_factory = factory


def _sta_init() -> Any:
    """Initialize COM STA apartment on the worker thread if pythoncom is available."""
    pycom_mod: Any = None
    try:
        import pythoncom  # type: ignore[import-untyped]

        pycom_mod = pythoncom
    except ImportError:
        pycom_mod = sys.modules.get("pythoncom")
    if pycom_mod is not None:
        try:
            pycom_mod.CoInitialize()
            return pycom_mod
        except Exception:
            return None
    return None


def _sta_uninit(pythoncom_mod: Any) -> None:
    """Uninitialize COM STA apartment on the worker thread."""
    if pythoncom_mod is not None:
        try:
            pythoncom_mod.CoUninitialize()
        except Exception:
            pass


def classify_error(exc: Exception) -> str:
    """Classify an exception into a safe standardized result code without leaking details."""
    err_str = str(exc).lower()
    if any(w in err_str for w in (
        "неверные имя", "пароль", "пользователь не найден", "идентификация",
        "authentication", "auth", "access denied", "неверный пароль", "ошибка аутентификации",
    )):
        return "auth_failed"
    if any(w in err_str for w in (
        "заблокирована", "блокировк", "locked", "exclusive", "монопольн",
    )):
        return "db_locked"
    if any(w in err_str for w in (
        "не найдена", "файл не найден", "not found", "1cv8.1cd",
    )):
        return "db_not_found"
    if any(w in err_str for w in (
        "invalid class string", "class not registered", "comconnector",
        "80040154", "800401f3", "не зарегистрирован", "platform unsupported",
    )):
        return "com_not_registered"
    return "unknown"


def _connect_worker(conn_str: str) -> str:
    """Execute connection in worker thread with COM STA apartment initialization."""
    pythoncom_mod = _sta_init()
    try:
        # Test seam for subprocess testing without real 1C
        if os.environ.get("_ONE_CHECK_TEST_MOCK") == "hang":
            hang_s = float(os.environ.get("_ONE_CHECK_TEST_HANG_SECONDS", "10.0"))
            time.sleep(hang_s)
            return "ok"

        if _test_connector_factory is not None:
            try:
                conn = _test_connector_factory(conn_str)
                del conn
                return "ok"
            except Exception as exc:
                return classify_error(exc)

        if sys.platform != "win32" and "win32com.client" not in sys.modules:
            return "com_not_registered"

        try:
            import win32com.client  # type: ignore[import-untyped]
        except ImportError:
            return "com_not_registered"

        try:
            connector = win32com.client.Dispatch("V83.COMConnector")
        except Exception as exc:
            code = classify_error(exc)
            return "com_not_registered" if code == "unknown" else code

        try:
            conn = connector.Connect(conn_str)
            # Successfully connected! Do not query metadata, documents, or registers.
            del conn
            del connector
            return "ok"
        except Exception as exc:
            return classify_error(exc)
    finally:
        _sta_uninit(pythoncom_mod)


def check_one_connection(
    db_path: str,
    user: str,
    password: str,
    timeout_seconds: float = 30.0,
) -> str:
    """Verify 1C file infobase connection within specified timeout.

    Returns one of: 'ok', 'com_not_registered', 'db_not_found', 'auth_failed', 'db_locked', 'timeout', 'unknown'.
    Never outputs or leaks passwords or connection strings.
    The worker thread runs with daemon=True so that hung 1C COM operations do not block process exit.
    """
    clean_path = db_path.strip()
    clean_user = user.strip()

    # Pre-check database directory existence for file bases
    if _test_connector_factory is None and not os.environ.get("_ONE_CHECK_TEST_MOCK"):
        p = Path(clean_path)
        if not p.is_dir() or not (p / "1Cv8.1CD").is_file():
            return "db_not_found"

    esc_path = clean_path.replace('"', '""')
    esc_user = clean_user.replace('"', '""')
    esc_pwd = password.replace('"', '""')
    conn_str = f'File="{esc_path}";Usr="{esc_user}";Pwd="{esc_pwd}";'

    result_queue: queue.Queue[str] = queue.Queue(maxsize=1)

    def _worker() -> None:
        try:
            res = _connect_worker(conn_str)
        except Exception as exc:
            res = classify_error(exc)
        result_queue.put(res)

    worker_thread = threading.Thread(
        target=_worker,
        name="OneCheckWorkerThread",
        daemon=True,
    )
    worker_thread.start()

    try:
        return result_queue.get(timeout=timeout_seconds)
    except queue.Empty:
        return "timeout"
