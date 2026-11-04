"""Unit tests for DPAPI-protected secrets handling in AgentSettings and CLI checks."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pytest
from pydantic import ValidationError

from poscenter_loyalty_agent.config import AgentSettings
from poscenter_loyalty_agent.dpapi import MockDPAPIBackend, set_dpapi_test_backend
from poscenter_loyalty_agent.main import cmd_check_config, cmd_status
from poscenter_loyalty_agent.state_store import StateStore


@pytest.fixture(autouse=True)
def setup_mock_dpapi():
    backend = MockDPAPIBackend()
    set_dpapi_test_backend(backend)
    yield
    set_dpapi_test_backend(None)


def test_dpapi_api_key_decrypted() -> None:
    backend = MockDPAPIBackend()
    plain_key = "a" * 20
    enc_key = backend.protect(plain_key)

    settings = AgentSettings(
        agent_env="production",
        agent_cloud_base_url="https://cloud.example.com",
        agent_api_key_dpapi=enc_key,
    )
    assert settings.agent_api_key == plain_key


def test_plaintext_api_key_logs_warning_without_value(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING)
    secret_key = "super_secret_agent_key_12345"

    AgentSettings(
        agent_env="development",
        agent_api_key=secret_key,
    )

    assert "AGENT_API_KEY: ключ хранится открытым текстом" in caplog.text
    # Ensure raw secret is NOT leaked in log
    assert secret_key not in caplog.text


def test_both_plaintext_and_dpapi_api_key_raises_error() -> None:
    backend = MockDPAPIBackend()
    enc_key = backend.protect("b" * 20)

    with pytest.raises(ValidationError, match="both AGENT_API_KEY.*AGENT_API_KEY_DPAPI"):
        AgentSettings(
            agent_api_key="a" * 20,
            agent_api_key_dpapi=enc_key,
        )


def test_dpapi_one_password_injected_into_connection_string() -> None:
    backend = MockDPAPIBackend()
    secret_pwd = 'P@ss"with"quotes'
    enc_pwd = backend.protect(secret_pwd)

    settings = AgentSettings(
        agent_api_key="a" * 20,
        one_connection_string='File="C:\\1C_data\\int";Usr="loyalty_ro";',
        one_password_dpapi=enc_pwd,
    )

    assert 'Pwd="P@ss""with""quotes";' in settings.one_connection_string
    assert 'File="C:\\1C_data\\int"' in settings.one_connection_string
    assert 'Usr="loyalty_ro"' in settings.one_connection_string


def test_plaintext_one_password_logs_warning_without_value(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING)
    secret_pwd = "raw_1c_password_value_999"

    AgentSettings(
        agent_api_key="a" * 20,
        one_connection_string=f'File="C:\\1C";Usr="u";Pwd="{secret_pwd}";',
    )

    assert "ONE_PASSWORD: пароль 1С хранится открытым текстом" in caplog.text
    assert secret_pwd not in caplog.text


def test_both_plaintext_and_dpapi_one_password_raises_error() -> None:
    backend = MockDPAPIBackend()
    enc_pwd = backend.protect("pass_dpapi")

    with pytest.raises(ValidationError, match="both plaintext 1C password and ONE_PASSWORD_DPAPI"):
        AgentSettings(
            agent_api_key="a" * 20,
            one_connection_string='File="C:\\1C";Usr="u";Pwd="plaintext_pwd";',
            one_password_dpapi=enc_pwd,
        )


def test_conflicting_one_passwords_raises_error() -> None:
    with pytest.raises(ValidationError, match="conflicting 1C passwords"):
        AgentSettings(
            agent_api_key="a" * 20,
            one_connection_string='File="C:\\1C";Usr="u";Pwd="pwd_one";',
            one_password="pwd_two",
        )


def test_repr_and_str_never_contain_secrets() -> None:
    backend = MockDPAPIBackend()
    api_key = "TOP_SECRET_API_KEY_77777777"
    enc_api_key = backend.protect(api_key)
    pwd_1c = "TOP_SECRET_1C_PASSWORD_8888"
    enc_pwd = backend.protect(pwd_1c)

    settings = AgentSettings(
        agent_api_key_dpapi=enc_api_key,
        one_connection_string='File="C:\\db";Usr="u";',
        one_password_dpapi=enc_pwd,
    )

    repr_str = repr(settings)
    str_val = str(settings)

    assert api_key not in repr_str
    assert enc_api_key not in repr_str
    assert pwd_1c not in repr_str
    assert enc_pwd not in repr_str

    assert api_key not in str_val
    assert enc_api_key not in str_val
    assert pwd_1c not in str_val
    assert enc_pwd not in str_val


def test_cli_check_config_and_status_no_secrets_leaked(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    backend = MockDPAPIBackend()
    api_key = "MY_AGENT_SECRET_KEY_99999"
    enc_api_key = backend.protect(api_key)
    pwd_1c = "MY_1C_SECRET_PWD_88888"
    enc_pwd = backend.protect(pwd_1c)

    db_file = tmp_path / "cli_dpapi.db"
    store = StateStore(db_file)
    store.record_error("Some operational issue")

    monkeypatch.setenv("AGENT_API_KEY_DPAPI", enc_api_key)
    monkeypatch.setenv("ONE_PASSWORD_DPAPI", enc_pwd)
    monkeypatch.setenv("ONE_CONNECTION_STRING", 'File="C:\\test";Usr="ro";')
    monkeypatch.setenv("AGENT_STATE_DB_PATH", str(db_file))

    # Test cmd_check_config
    exit_code = cmd_check_config(argparse.Namespace())
    assert exit_code == 0
    captured_check = capsys.readouterr().out
    assert api_key not in captured_check
    assert enc_api_key not in captured_check
    assert pwd_1c not in captured_check
    assert enc_pwd not in captured_check

    # Test cmd_status
    exit_code = cmd_status(argparse.Namespace())
    assert exit_code == 0
    captured_status = capsys.readouterr().out
    assert api_key not in captured_status
    assert enc_api_key not in captured_status
    assert pwd_1c not in captured_status
    assert enc_pwd not in captured_status
