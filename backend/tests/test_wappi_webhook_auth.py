import json

import pytest
from httpx import AsyncClient

from app.core.config import settings


@pytest.mark.asyncio
async def test_wappi_webhook_missing_auth_header_returns_401(client: AsyncClient) -> None:
    """Missing webhook secret header must be rejected with 401."""
    resp = await client.post(
        "/webhooks/wappi",
        json={"messages": []},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_WEBHOOK_AUTH"


@pytest.mark.asyncio
async def test_wappi_webhook_invalid_secret_returns_401(client: AsyncClient) -> None:
    """Invalid secret in webhook header must be rejected with 401."""
    resp = await client.post(
        "/webhooks/wappi",
        headers={settings.wappi_webhook_auth_header: "wrong_secret_12345"},
        json={"messages": []},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_WEBHOOK_AUTH"


@pytest.mark.asyncio
async def test_wappi_webhook_valid_secret_returns_200(client: AsyncClient) -> None:
    """Valid secret in webhook header returns 200 OK."""
    resp = await client.post(
        "/webhooks/wappi",
        headers={settings.wappi_webhook_auth_header: settings.wappi_webhook_auth_secret},
        json={"messages": []},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["processed"] == 0


@pytest.mark.asyncio
async def test_wappi_webhook_custom_header_name(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Authentication uses dynamically configured header name."""
    monkeypatch.setattr(settings, "wappi_webhook_auth_header", "X-Custom-Wappi-Token")
    monkeypatch.setattr(settings, "wappi_webhook_auth_secret", "custom_secret_value_12345678901234567890")

    # Old header must now fail
    resp_fail = await client.post(
        "/webhooks/wappi",
        headers={"X-Old-Unconfigured-Header": "custom_secret_value_12345678901234567890"},
        json={"messages": []},
    )
    assert resp_fail.status_code == 401

    # New header succeeds
    resp_ok = await client.post(
        "/webhooks/wappi",
        headers={"X-Custom-Wappi-Token": "custom_secret_value_12345678901234567890"},
        json={"messages": []},
    )
    assert resp_ok.status_code == 200
    assert resp_ok.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_wappi_webhook_payload_too_large_content_length_returns_413(
    client: AsyncClient,
) -> None:
    """Payload with Content-Length exceeding max limit returns 413."""
    headers = {
        settings.wappi_webhook_auth_header: settings.wappi_webhook_auth_secret,
        "content-length": str(settings.wappi_webhook_max_body_bytes + 100),
    }
    resp = await client.post(
        "/webhooks/wappi",
        headers=headers,
        content=b"{}",
    )
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


@pytest.mark.asyncio
async def test_wappi_webhook_payload_too_large_body_bytes_returns_413(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Payload exceeding max limit returns 413 even without content-length header."""
    monkeypatch.setattr(settings, "wappi_webhook_max_body_bytes", 50)
    large_payload = json.dumps({"messages": [{"id": "x" * 100}]}).encode()
    resp = await client.post(
        "/webhooks/wappi",
        headers={settings.wappi_webhook_auth_header: settings.wappi_webhook_auth_secret},
        content=large_payload,
    )
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


@pytest.mark.asyncio
async def test_wappi_webhook_chunked_body_over_limit_stops_early_with_413(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Chunked upload (no Content-Length) is cut off at the limit instead of being buffered fully."""
    monkeypatch.setattr(settings, "wappi_webhook_max_body_bytes", 100)
    chunks_sent = 0

    async def body_stream():  # type: ignore[no-untyped-def]
        nonlocal chunks_sent
        for _ in range(1000):
            chunks_sent += 1
            yield b"x" * 50

    resp = await client.post(
        "/webhooks/wappi",
        headers={settings.wappi_webhook_auth_header: settings.wappi_webhook_auth_secret},
        content=body_stream(),
    )
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert "content-length" not in resp.request.headers
    assert chunks_sent < 1000


@pytest.mark.asyncio
async def test_wappi_webhook_invalid_json_returns_400(client: AsyncClient) -> None:
    """Non-JSON payload returns 400 Bad Request."""
    resp = await client.post(
        "/webhooks/wappi",
        headers={settings.wappi_webhook_auth_header: settings.wappi_webhook_auth_secret},
        content=b"not a valid json {{{",
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_JSON_PAYLOAD"
