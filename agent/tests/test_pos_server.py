"""Real loopback HTTP tests with an exclusively mocked cloud and isolated paths."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import socket
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from poscenter_loyalty_agent.cloud_client import FakeCloudClient
from poscenter_loyalty_agent.config import AgentSettings
from poscenter_loyalty_agent.main import cmd_check_config, cmd_status
from poscenter_loyalty_agent.pos_server import PosRateLimiter, PosServer
from poscenter_loyalty_agent.runtime import AgentRuntime
from poscenter_loyalty_agent.source import FakeLoyaltySource

POS_PASSWORD = "pos-fixture-password-" + "p" * 32
AGENT_KEY = "agent-fixture-key-not-a-real-key"
TOKEN = "C1" + "ABCDEFGHIJKLMNOPQRSTUV234567" * 2
BARCODE = "0000123456789"


def settings_for(tmp_path: Path, **overrides: Any) -> AgentSettings:
    values: dict[str, Any] = {
        "agent_env": "test",
        "agent_api_key": AGENT_KEY,
        "agent_cloud_base_url": "https://cloud.invalid",
        "agent_pos_server_enabled": True,
        "agent_pos_listen_host": "127.0.0.1",
        "agent_pos_token": SecretStr(POS_PASSWORD),
        "agent_state_db_path": tmp_path / "state.db",
        "one_state_key_path": tmp_path / "state.key",
        "agent_log_dir": tmp_path / "logs",
        "one_mapping_path": tmp_path / "mapping.json",
        "one_adapter_mode": "fake",
        "agent_shutdown_grace_seconds": 0,
    }
    values.update(overrides)
    return AgentSettings(_env_file=None, **values)


@contextmanager
def running_server(
    tmp_path: Path,
    cloud_handler: Callable[[httpx.Request], httpx.Response] | None = None,
    **overrides: Any,
) -> Iterator[tuple[httpx.Client, list[httpx.Request], PosServer]]:
    calls: list[httpx.Request] = []

    def mocked_cloud(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if cloud_handler is not None:
            return cloud_handler(request)
        return httpx.Response(200, json={"barcode": BARCODE, "card_id": "fixture-private-id"})

    service = PosServer(
        settings_for(tmp_path, **overrides),
        listen_port=0,
        transport=httpx.MockTransport(mocked_cloud),
    )
    assert service.start()
    assert service.address is not None
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{service.address[1]}",
            headers={"X-Pos-Token": POS_PASSWORD}, timeout=4, trust_env=False,
        ) as client:
            yield client, calls, service
    finally:
        service.stop()


def assert_error(response: httpx.Response, status: int, code: str) -> None:
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert isinstance(response.json()["error"]["message"], str)
    assert "Python" not in response.headers["Server"]


def test_resolve_preserves_zeros_and_sends_only_agent_key_to_cloud(tmp_path: Path) -> None:
    with running_server(tmp_path) as (client, calls, _):
        response = client.post("/v1/qr/resolve", json={"token": TOKEN})
        assert response.status_code == 200
        assert response.json() == {"barcode": BARCODE}
        assert response.headers["Cache-Control"] == "no-store"
        assert response.headers["Server"] == "POSCENTER-POS"
        assert len(calls) == 1
        assert str(calls[0].url) == "https://cloud.invalid/agent/qr/resolve"
        assert calls[0].headers["X-Agent-Key"] == AGENT_KEY
        assert "X-Pos-Token" not in calls[0].headers
        assert json.loads(calls[0].content) == {"token": TOKEN}
    # Standalone POS must not instantiate or modify state/key/log directories.
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("password", [None, "incorrect-fixture-password"])
def test_missing_or_wrong_password(tmp_path: Path, password: str | None) -> None:
    with running_server(tmp_path) as (client, calls, _):
        client.headers.pop("X-Pos-Token")
        headers = {"X-Pos-Token": password} if password is not None else {}
        assert_error(client.get("/v1/health", headers=headers), 401, "POS_UNAUTHORIZED")
        assert calls == []


def test_forbidden_network_checked_before_password_and_ignores_forwarded_ip(tmp_path: Path) -> None:
    with running_server(tmp_path, agent_pos_allowed_networks="10.0.0.0/8") as (client, calls, _):
        assert_error(client.get("/v1/health", headers={"X-Forwarded-For": "10.0.0.1"}), 403, "POS_FORBIDDEN")
        assert calls == []


@pytest.mark.parametrize("token", ["", "C1short", "C1" + "A" * 19, "C1" + "A" * 121, "C1" + "a" * 30, TOKEN + "\n", 123, None])
def test_malformed_token_never_calls_cloud(tmp_path: Path, token: object) -> None:
    with running_server(tmp_path) as (client, calls, _):
        assert_error(client.post("/v1/qr/resolve", json={"token": token}), 400, "QR_TOKEN_MALFORMED")
        assert calls == []


@pytest.mark.parametrize("cloud_status,status,code", [
    (422, 422, "QR_TOKEN_INVALID"), (401, 502, "AGENT_NOT_AUTHORIZED"),
    (403, 502, "AGENT_NOT_AUTHORIZED"), (500, 502, "CLOUD_ERROR"),
    (429, 502, "CLOUD_ERROR"), (302, 502, "CLOUD_ERROR"),
])
def test_cloud_status_mapping_and_no_retry(tmp_path: Path, cloud_status: int, status: int, code: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(cloud_status, json={"sensitive": TOKEN}, headers={"Location": "https://other.invalid"})

    with running_server(tmp_path, handler) as (client, calls, _):
        response = client.post("/v1/qr/resolve", json={"token": TOKEN})
        assert_error(response, status, code)
        assert TOKEN not in response.text
        assert len(calls) == 1


@pytest.mark.parametrize("error_type,status,code", [
    (httpx.ReadTimeout, 504, "CLOUD_TIMEOUT"), (httpx.ConnectError, 503, "CLOUD_UNAVAILABLE"),
])
def test_cloud_transport_errors(tmp_path: Path, error_type: type[httpx.RequestError], status: int, code: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise error_type(TOKEN + POS_PASSWORD + AGENT_KEY, request=request)

    with running_server(tmp_path, handler) as (client, calls, _):
        response = client.post("/v1/qr/resolve", json={"token": TOKEN})
        assert_error(response, status, code)
        assert TOKEN not in response.text
        assert POS_PASSWORD not in response.text
        assert AGENT_KEY not in response.text
        assert len(calls) == 1


@pytest.mark.parametrize(
    "body",
    [
        {"barcode": 123456},
        {"barcode": "abc"},
        {},
        [],
        {"barcode": "1" * 14},
        {"barcode": "1" * 16},
    ],
)
def test_bad_cloud_schema_is_not_a_success(tmp_path: Path, body: object) -> None:
    with running_server(tmp_path, lambda _: httpx.Response(200, json=body)) as (client, calls, _):
        assert_error(client.post("/v1/qr/resolve", json={"token": TOKEN}), 502, "CLOUD_ERROR")
        assert len(calls) == 1


def test_non_json_cloud_response(tmp_path: Path) -> None:
    with running_server(tmp_path, lambda _: httpx.Response(200, text="invalid-json")) as (client, _, _):
        assert_error(client.post("/v1/qr/resolve", json={"token": TOKEN}), 502, "CLOUD_ERROR")


def test_rate_limit_60_all_requests_and_10_failed_passwords(tmp_path: Path) -> None:
    with running_server(tmp_path) as (client, calls, _):
        for _ in range(60):
            assert client.get("/v1/health").status_code == 200
        assert_error(client.get("/v1/health"), 429, "POS_RATE_LIMITED")
        assert calls == []
    with running_server(tmp_path) as (client, _, _):
        for _ in range(10):
            assert client.get("/v1/health", headers={"X-Pos-Token": "wrong"}).status_code == 401
        assert_error(client.get("/v1/health", headers={"X-Pos-Token": "wrong"}), 429, "POS_RATE_LIMITED")


def test_rate_limit_window_expiry_and_per_address() -> None:
    now = [0.0]
    limiter = PosRateLimiter(clock=lambda: now[0])
    assert all(limiter.allow("first", False) for _ in range(10))
    assert not limiter.allow("first", False)
    assert limiter.allow("other", False)
    now[0] = 60.0
    assert limiter.allow("first", False)


def test_size_content_type_and_json_validation(tmp_path: Path) -> None:
    with running_server(tmp_path) as (client, calls, _):
        assert_error(client.post("/v1/qr/resolve", content=b"x" * 1025, headers={"Content-Type": "application/json"}), 413, "POS_BODY_TOO_LARGE")
        assert_error(client.post("/v1/qr/resolve", content=b"{}", headers={"Content-Type": "text/plain"}), 415, "POS_UNSUPPORTED_MEDIA_TYPE")
        assert_error(client.post("/v1/qr/resolve", content=b"{", headers={"Content-Type": "application/json"}), 400, "POS_BAD_REQUEST")
        assert calls == []


def test_health_does_not_call_cloud_and_unknown_route_is_safe(tmp_path: Path) -> None:
    with running_server(tmp_path) as (client, calls, _):
        assert client.get("/v1/health").json() == {"status": "ok"}
        assert_error(client.get("/unknown?secret=" + TOKEN), 404, "POS_NOT_FOUND")
        assert calls == []


def test_socket_read_timeout_and_duplicate_password_rejection(tmp_path: Path) -> None:
    with running_server(tmp_path) as (client, calls, service):
        assert_error(client.get("/v1/health", headers=[("X-Pos-Token", POS_PASSWORD), ("X-Pos-Token", POS_PASSWORD)]), 401, "POS_UNAUTHORIZED")
        assert service.address is not None
        with socket.create_connection(service.address, timeout=4) as connection:
            request = (
                "POST /v1/qr/resolve HTTP/1.0\r\n"
                f"X-Pos-Token: {POS_PASSWORD}\r\nContent-Type: application/json\r\n"
                "Content-Length: 10\r\n\r\n{"
            )
            connection.sendall(request.encode())
            assert b"408" in connection.recv(4096)
        assert calls == []


def test_default_disabled_never_opens_a_socket(tmp_path: Path) -> None:
    settings = AgentSettings(_env_file=None, agent_state_db_path=tmp_path / "state.db")
    assert not settings.agent_pos_server_enabled
    service = PosServer(settings)
    with patch("poscenter_loyalty_agent.pos_server._PosHTTPServer") as server_type:
        assert not service.start()
        server_type.assert_not_called()
    assert service.address is None
    service.stop()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("token", ["", "short", "x" * 31, "x" * 32 + "\n"])
def test_check_config_rejects_bad_password_without_leaking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], token: str,
) -> None:
    monkeypatch.setenv("AGENT_POS_SERVER_ENABLED", "true")
    monkeypatch.setenv("AGENT_POS_TOKEN", token)
    monkeypatch.setenv("AGENT_STATE_DB_PATH", str(tmp_path / "state.db"))
    assert cmd_check_config(argparse.Namespace()) == 1
    output = capsys.readouterr().err
    assert "AGENT_POS_TOKEN" in output
    if token:
        assert token not in output
    assert not (tmp_path / "state.db").exists()


@pytest.mark.parametrize("overrides,field", [
    ({"agent_pos_allowed_networks": "invalid"}, "AGENT_POS_ALLOWED_NETWORKS"),
    ({"agent_pos_allowed_networks": ""}, "AGENT_POS_ALLOWED_NETWORKS"),
    ({"agent_pos_allowed_networks": "192.168.1.9/24"}, "AGENT_POS_ALLOWED_NETWORKS"),
    ({"agent_pos_listen_host": "not-a-host"}, "AGENT_POS_LISTEN_HOST"),
    ({"agent_pos_listen_port": 0}, "AGENT_POS_LISTEN_PORT"),
    ({"agent_pos_listen_port": 65536}, "AGENT_POS_LISTEN_PORT"),
])
def test_enabled_config_validation(tmp_path: Path, overrides: dict[str, object], field: str) -> None:
    with pytest.raises(ValidationError) as caught:
        settings_for(tmp_path, **overrides)
    assert field in str(caught.value)
    assert POS_PASSWORD not in str(caught.value)
    assert AGENT_KEY not in str(caught.value)


def test_status_and_settings_repr_do_not_show_pos_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    settings = settings_for(tmp_path)
    monkeypatch.setattr("poscenter_loyalty_agent.main.get_settings", lambda: settings)
    assert cmd_status(argparse.Namespace()) == 0
    output = capsys.readouterr().out
    assert "POS-сервис: включён, 127.0.0.1:8765" in output
    assert POS_PASSWORD not in output + repr(settings) + settings.model_dump_json()
    disabled = settings_for(tmp_path, agent_pos_server_enabled=False)
    monkeypatch.setattr("poscenter_loyalty_agent.main.get_settings", lambda: disabled)
    assert cmd_status(argparse.Namespace()) == 0
    assert "POS-сервис: выключен" in capsys.readouterr().out


def test_logs_never_contain_full_tokens_secrets_or_barcode(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    with running_server(tmp_path) as (client, _, _):
        assert client.post("/v1/qr/resolve", json={"token": TOKEN}).status_code == 200
        client.get("/bad?secret=" + POS_PASSWORD)
        client.post("/v1/qr/resolve", json={"token": TOKEN + "\n"})
    # The test's HTTP client may log its own deliberately malicious URL.
    # Check the agent's records, including raw pre-formatter messages.
    agent_logs = "\n".join(record.getMessage() for record in caplog.records if record.name.startswith("poscenter_loyalty_agent"))
    for secret in (TOKEN, POS_PASSWORD, AGENT_KEY, BARCODE):
        assert secret not in agent_logs
    assert f"prefix={TOKEN[:4]}, length={len(TOKEN)}" in agent_logs
    assert f"barcode suffix={BARCODE[-4:]}" in agent_logs


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_bind", [False, True])
async def test_runtime_pos_lifecycle_and_bind_failure_do_not_break_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fail_bind: bool,
) -> None:
    settings = settings_for(tmp_path)
    service = PosServer(settings, listen_port=0, transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"barcode": BARCODE})))
    monkeypatch.setattr("poscenter_loyalty_agent.runtime.PosServer", lambda _: service)
    monkeypatch.setattr(AgentRuntime, "_setup_signals", lambda _: None)
    cloud = FakeCloudClient()
    source = FakeLoyaltySource()
    runtime = AgentRuntime(settings, cloud_client=cloud, source=source)
    task: asyncio.Task[None] | None = None
    try:
        with patch("poscenter_loyalty_agent.pos_server._PosHTTPServer", side_effect=OSError("bind fixture")) if fail_bind else _no_patch():
            task = asyncio.create_task(runtime.run())
            for _ in range(100):
                if cloud.heartbeats:
                    break
                await asyncio.sleep(0.02)
            assert cloud.heartbeats
            assert runtime.is_running
            if not fail_bind:
                assert service.address is not None
                with httpx.Client(trust_env=False) as client:
                    response = await asyncio.to_thread(client.get, f"http://127.0.0.1:{service.address[1]}/v1/health", headers={"X-Pos-Token": POS_PASSWORD})
                assert response.status_code == 200
            else:
                assert service.address is None
    finally:
        runtime.request_stop()
        if task is not None:
            await asyncio.wait_for(task, timeout=4)
    assert service.address is None
    assert cloud.is_closed and source.is_closed


@pytest.mark.asyncio
async def test_sync_failure_does_not_stop_pos_or_heartbeat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = settings_for(tmp_path)
    service = PosServer(settings, listen_port=0, transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"barcode": BARCODE})))
    monkeypatch.setattr("poscenter_loyalty_agent.runtime.PosServer", lambda _: service)
    monkeypatch.setattr(AgentRuntime, "_setup_signals", lambda _: None)
    cloud = FakeCloudClient()
    source = FakeLoyaltySource()
    source.cards_error = RuntimeError("synthetic sync failure")
    runtime = AgentRuntime(settings, cloud_client=cloud, source=source)
    task = asyncio.create_task(runtime.run())
    try:
        for _ in range(100):
            if runtime.state_store.get_status().last_error and cloud.heartbeats:
                break
            await asyncio.sleep(0.02)
        assert runtime.state_store.get_status().last_error
        assert cloud.heartbeats
        assert service.address is not None
        with httpx.Client(trust_env=False) as client:
            response = await asyncio.to_thread(client.get, f"http://127.0.0.1:{service.address[1]}/v1/health", headers={"X-Pos-Token": POS_PASSWORD})
        assert response.status_code == 200
    finally:
        runtime.request_stop()
        await asyncio.wait_for(task, timeout=4)


@contextmanager
def _no_patch() -> Iterator[None]:
    yield
