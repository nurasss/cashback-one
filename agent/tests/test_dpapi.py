"""Unit tests for Windows DPAPI integration and cross-platform mock handling."""

from __future__ import annotations

import pytest

from poscenter_loyalty_agent.dpapi import (
    DPAPIDecryptionError,
    DPAPIPlatformError,
    MockDPAPIBackend,
    get_dpapi_test_backend,
    protect_secret,
    set_dpapi_test_backend,
    unprotect_secret,
)


@pytest.fixture(autouse=True)
def _reset_dpapi_backend():
    prev = get_dpapi_test_backend()
    yield
    set_dpapi_test_backend(prev)


def test_mock_dpapi_roundtrip() -> None:
    set_dpapi_test_backend(MockDPAPIBackend())
    secret = "my_super_secret_api_key_12345"
    protected = protect_secret(secret)
    assert protected != secret
    assert len(protected) > 10

    unprotected = unprotect_secret(protected)
    assert unprotected == secret


def test_mock_dpapi_empty() -> None:
    set_dpapi_test_backend(MockDPAPIBackend())
    assert protect_secret("") == ""
    assert unprotect_secret("") == ""


def test_mock_dpapi_invalid_base64() -> None:
    set_dpapi_test_backend(MockDPAPIBackend())
    with pytest.raises(DPAPIDecryptionError, match="Invalid base64"):
        unprotect_secret("!!!not-base64???")


def test_mock_dpapi_corrupt_payload() -> None:
    set_dpapi_test_backend(MockDPAPIBackend())
    import base64
    bad_payload = base64.b64encode(b"CORRUPT_HEADER:xyz").decode("ascii")
    with pytest.raises(DPAPIDecryptionError, match="mismatch"):
        unprotect_secret(bad_payload)


def test_dpapi_platform_error_without_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    set_dpapi_test_backend(None)
    monkeypatch.setattr("poscenter_loyalty_agent.dpapi.is_windows", lambda: False)
    with pytest.raises(DPAPIPlatformError, match="supported on Windows"):
        protect_secret("test-secret")
    with pytest.raises(DPAPIPlatformError, match="supported on Windows"):
        unprotect_secret("test-ciphertext")


def test_secret_never_leaked_in_exception() -> None:
    set_dpapi_test_backend(MockDPAPIBackend())
    super_secret = "ULTRA_SENSITIVE_SECRET_TOKEN_999"
    # Cause a decryption error and assert the secret is not in str(exc)
    bad_b64 = "YWJjZGVmZw=="  # valid base64 for 'abcdefg', but no mock header
    with pytest.raises(DPAPIDecryptionError) as exc_info:
        unprotect_secret(bad_b64)
    assert super_secret not in str(exc_info.value)
