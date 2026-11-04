"""Windows Data Protection API (DPAPI) integration for POSCENTER Loyalty Agent.

CRITICAL SECURITY AND DESIGN CONSTRAINTS:
1. Windows DPAPI is used to encrypt sensitive configuration credentials (AGENT_API_KEY, 1C infobase password).
2. Scope is CRYPTPROTECT_LOCAL_MACHINE with application-specific entropy:
   - The installer runs elevated as Administrator.
   - The Windows Service runs as LocalSystem (NT AUTHORITY\\SYSTEM).
   - Machine scope allows credentials protected by the installer to be unprotected by the service.
   - Machine-scope DPAPI protects credentials when the configuration file is copied to another
     computer or read accidentally from backups/exports.
   - Against a local Administrator or any process with read access to .env.service on the same machine,
     protection is provided strictly by exact DACL (SYSTEM and Administrators only).
   - Application-specific entropy is not a secret (the repository is public); it serves only to
     partition/isolate agent data from other applications on the system.
   - Exact DACL on the containing directory and file (SYSTEM and Administrators only) provides
     the primary local access barrier.
3. Cross-platform safe:
   - On Windows, crypt32.dll is used via ctypes with proper LocalFree cleanup.
   - On non-Windows (macOS/Linux), a test backend can be injected via set_dpapi_test_backend()
     or MockDPAPIBackend for automated testing.
   - When not on Windows and no mock is set, operations raise DPAPIPlatformError.
4. Secrets are NEVER logged or included in exception messages.
"""

from __future__ import annotations

import base64
import binascii
import logging
import sys
from typing import Protocol

logger = logging.getLogger(__name__)

# Application-specific entropy (not a secret; partitions agent data from other applications).
DPAPI_ENTROPY: bytes = b"POSCENTER_LOYALTY_AGENT_DPAPI_SALT_v1"

# Win32 DPAPI constants
CRYPTPROTECT_UI_FORBIDDEN: int = 0x00000001
CRYPTPROTECT_LOCAL_MACHINE: int = 0x00000004


class DPAPIError(RuntimeError):
    """Base exception for DPAPI operations."""


class DPAPIPlatformError(DPAPIError):
    """Raised when DPAPI operations are attempted on an unsupported platform without mock."""


class DPAPIDecryptionError(DPAPIError):
    """Raised when DPAPI decryption fails (corrupt data, invalid machine, wrong entropy)."""


class DPAPIBackend(Protocol):
    def protect(self, plain_text: str) -> str:
        ...

    def unprotect(self, cipher_text_b64: str) -> str:
        ...


class MockDPAPIBackend:
    """Deterministic mock DPAPI implementation for testing on non-Windows platforms."""

    def __init__(self, entropy: bytes = DPAPI_ENTROPY) -> None:
        self.entropy = entropy

    def protect(self, plain_text: str) -> str:
        if not plain_text:
            return ""
        # XOR with entropy for test simulation, prefixed with marker
        raw = plain_text.encode("utf-8")
        ent_len = len(self.entropy)
        masked = bytes(b ^ self.entropy[i % ent_len] for i, b in enumerate(raw))
        payload = b"MOCK_DPAPI:" + masked
        return base64.b64encode(payload).decode("ascii")

    def unprotect(self, cipher_text_b64: str) -> str:
        clean = cipher_text_b64.strip()
        if not clean:
            return ""
        try:
            payload = base64.b64decode(clean, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise DPAPIDecryptionError("Invalid base64 encoding in DPAPI secret") from exc

        if not payload.startswith(b"MOCK_DPAPI:"):
            raise DPAPIDecryptionError("DPAPI payload header mismatch")

        masked = payload[len(b"MOCK_DPAPI:"):]
        ent_len = len(self.entropy)
        plain = bytes(b ^ self.entropy[i % ent_len] for i, b in enumerate(masked))
        try:
            return plain.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DPAPIDecryptionError("Decrypted DPAPI payload is not valid UTF-8") from exc


_test_backend: DPAPIBackend | None = None


def set_dpapi_test_backend(backend: DPAPIBackend | None) -> None:
    """Set custom DPAPI backend for testing purposes."""
    global _test_backend
    _test_backend = backend


def get_dpapi_test_backend() -> DPAPIBackend | None:
    """Retrieve currently active test backend."""
    return _test_backend


def is_windows() -> bool:
    """Return True if running on native Windows."""
    return sys.platform == "win32"


def _win32_protect(plain_bytes: bytes, entropy: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_byte)),
        ]

    crypt32 = ctypes.windll.crypt32  # type: ignore[attr-defined]
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel32.LocalFree.restype = wintypes.HLOCAL

    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(DATA_BLOB),
        wintypes.LPCWSTR,
        ctypes.POINTER(DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(DATA_BLOB),
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL

    in_buf = (ctypes.c_byte * len(plain_bytes))(*plain_bytes)
    in_blob = DATA_BLOB(len(plain_bytes), ctypes.cast(in_buf, ctypes.POINTER(ctypes.c_byte)))

    ent_buf = (ctypes.c_byte * len(entropy))(*entropy)
    ent_blob = DATA_BLOB(len(entropy), ctypes.cast(ent_buf, ctypes.POINTER(ctypes.c_byte)))

    out_blob = DATA_BLOB(0, ctypes.POINTER(ctypes.c_byte)())

    flags = CRYPTPROTECT_LOCAL_MACHINE | CRYPTPROTECT_UI_FORBIDDEN

    success = crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        None,
        ctypes.byref(ent_blob),
        None,
        None,
        flags,
        ctypes.byref(out_blob),
    )
    if not success:
        err = ctypes.GetLastError()  # type: ignore[attr-defined]
        raise DPAPIError(f"CryptProtectData failed with Win32 error code: {err}")

    try:
        raw_cipher = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        return raw_cipher
    finally:
        if out_blob.pbData:
            kernel32.LocalFree(out_blob.pbData)


def _win32_unprotect(cipher_bytes: bytes, entropy: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_byte)),
        ]

    crypt32 = ctypes.windll.crypt32  # type: ignore[attr-defined]
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel32.LocalFree.restype = wintypes.HLOCAL

    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(DATA_BLOB),
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(DATA_BLOB),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL

    in_buf = (ctypes.c_byte * len(cipher_bytes))(*cipher_bytes)
    in_blob = DATA_BLOB(len(cipher_bytes), ctypes.cast(in_buf, ctypes.POINTER(ctypes.c_byte)))

    ent_buf = (ctypes.c_byte * len(entropy))(*entropy)
    ent_blob = DATA_BLOB(len(entropy), ctypes.cast(ent_buf, ctypes.POINTER(ctypes.c_byte)))

    out_blob = DATA_BLOB(0, ctypes.POINTER(ctypes.c_byte)())

    flags = CRYPTPROTECT_UI_FORBIDDEN

    success = crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        ctypes.byref(ent_blob),
        None,
        None,
        flags,
        ctypes.byref(out_blob),
    )
    if not success:
        err = ctypes.GetLastError()  # type: ignore[attr-defined]
        raise DPAPIDecryptionError(f"CryptUnprotectData failed with Win32 error code: {err}")

    try:
        raw_plain = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        return raw_plain
    finally:
        if out_blob.pbData:
            kernel32.LocalFree(out_blob.pbData)


def protect_secret(plain_text: str, entropy: bytes = DPAPI_ENTROPY) -> str:
    """Encrypt a plain text secret using Windows DPAPI (machine scope + application entropy).

    Returns a Base64-encoded string representation of the ciphertext.
    Never includes secret values in errors or logs.
    """
    if _test_backend is not None:
        return _test_backend.protect(plain_text)

    if not is_windows():
        raise DPAPIPlatformError(
            "Windows DPAPI is only supported on Windows. Configure a test backend for non-Windows execution."
        )

    if not plain_text:
        return ""

    plain_bytes = plain_text.encode("utf-8")
    cipher_bytes = _win32_protect(plain_bytes, entropy)
    return base64.b64encode(cipher_bytes).decode("ascii")


def unprotect_secret(cipher_text_b64: str, entropy: bytes = DPAPI_ENTROPY) -> str:
    """Decrypt a Base64-encoded DPAPI ciphertext using Windows DPAPI.

    Returns the decrypted plain text string.
    Never includes secret values or ciphertext in errors or logs.
    """
    if _test_backend is not None:
        return _test_backend.unprotect(cipher_text_b64)

    if not is_windows():
        raise DPAPIPlatformError(
            "Windows DPAPI is only supported on Windows. Configure a test backend for non-Windows execution."
        )

    clean_b64 = cipher_text_b64.strip()
    if not clean_b64:
        return ""

    try:
        cipher_bytes = base64.b64decode(clean_b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise DPAPIDecryptionError("Invalid base64 encoding in DPAPI secret") from exc

    plain_bytes = _win32_unprotect(cipher_bytes, entropy)
    try:
        return plain_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DPAPIDecryptionError("Decrypted DPAPI secret is not valid UTF-8") from exc
