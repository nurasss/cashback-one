"""Tests for CloudClient implementations, HTTP error classifications, and protocol errors."""

from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from poscenter_loyalty_agent.cloud_client import (
    CloudAuthError,
    CloudNonRetryableError,
    CloudProtocolError,
    CloudRetryableError,
    FakeCloudClient,
    HttpCloudClient,
)
from poscenter_loyalty_agent.models import (
    CardsSyncPayload,
    CardSyncItem,
    HeartbeatPayload,
    TransactionsSyncPayload,
    TransactionSyncItem,
)


@pytest.mark.asyncio
async def test_fake_cloud_client_records_payloads() -> None:
    fake = FakeCloudClient()
    now = datetime(2026, 9, 29, 10, 0, 0, tzinfo=UTC)

    card = CardSyncItem(
        barcode="1234567890123",
        phone="+77011234567",
        full_name="Ivan Ivanov",
        balance=Decimal("150.00"),
        is_blocked=False,
        updated_at=now,
    )
    cards_ack = await fake.sync_cards(CardsSyncPayload(cards=[card]))
    assert cards_ack.received == 1
    assert cards_ack.created == 1
    assert len(fake.synced_cards) == 1

    tx = TransactionSyncItem(
        external_id="ext-tx-1",
        barcode="1234567890123",
        type="accrual",
        amount=Decimal("50.00"),
        balance_after=Decimal("150.00"),
        occurred_at=now,
    )
    tx_ack = await fake.sync_transactions(TransactionsSyncPayload(transactions=[tx]))
    assert tx_ack.received == 1
    assert tx_ack.created == 1
    assert len(fake.synced_transactions) == 1

    hb_ack = await fake.send_heartbeat(HeartbeatPayload(version="0.1.0", error=None))
    assert hb_ack.status == "ok"
    assert len(fake.heartbeats) == 1

    await fake.close()
    assert fake.is_closed


@pytest.mark.asyncio
async def test_http_client_error_classification() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url_path = request.url.path
        if url_path == "/agent/sync/auth-fail":
            return httpx.Response(401, json={"detail": "Invalid agent API key"})
        if url_path == "/agent/sync/rate-limited":
            return httpx.Response(429, headers={"Retry-After": "15"}, json={"detail": "Too many requests"})
        if url_path == "/agent/sync/server-error":
            return httpx.Response(503, json={"detail": "Backend unavailable"})
        if url_path == "/agent/sync/bad-request":
            return httpx.Response(422, json={"detail": "Unprocessable entity"})
        return httpx.Response(200, json={"received": 0, "created": 0, "updated": 0, "ignored_stale": 0})

    transport = httpx.MockTransport(handler)
    client = HttpCloudClient(
        base_url="http://test-cloud",
        api_key="secret-key",
    )
    client._client = httpx.AsyncClient(
        base_url="http://test-cloud",
        transport=transport,
        headers={"X-Agent-Key": "secret-key"},
    )

    # 401 Unauthorized -> CloudAuthError
    resp = await client._client.post("/agent/sync/auth-fail")
    with pytest.raises(CloudAuthError, match="401"):
        client._handle_response_error(resp)

    # 429 Rate Limited -> CloudRetryableError with retry_after
    resp = await client._client.post("/agent/sync/rate-limited")
    with pytest.raises(CloudRetryableError) as exc_info:
        client._handle_response_error(resp)
    assert exc_info.value.retry_after == 15.0

    # 503 Service Unavailable -> CloudRetryableError
    resp = await client._client.post("/agent/sync/server-error")
    with pytest.raises(CloudRetryableError, match="503"):
        client._handle_response_error(resp)

    # 422 Bad Request -> CloudNonRetryableError
    resp = await client._client.post("/agent/sync/bad-request")
    with pytest.raises(CloudNonRetryableError, match="422"):
        client._handle_response_error(resp)

    await client.close()


@pytest.mark.asyncio
async def test_cloud_protocol_error_on_malformed_2xx_responses() -> None:
    """If Cloud returns 200 with invalid JSON or missing fields, CloudProtocolError must be raised."""
    responses = {
        "/cards/bad_json": httpx.Response(200, text="NOT_VALID_JSON{"),
        "/cards/missing_fields": httpx.Response(200, json={"received": 5}),  # missing created, updated, etc.
        "/tx/bad_json": httpx.Response(200, text="<html>Proxy Error</html>"),
        "/hb/bad_json": httpx.Response(200, json={}),  # missing status
    }

    def handler(request: httpx.Request) -> httpx.Response:
        p = request.url.path
        if "/agent/sync/cards" in p:
            return responses.get(request.headers.get("X-Test-Route", "/cards/bad_json"), responses["/cards/bad_json"])
        if "/agent/sync/transactions" in p:
            return responses["/tx/bad_json"]
        if "/agent/sync/heartbeat" in p:
            return responses["/hb/bad_json"]
        return httpx.Response(200, json={"status": "ok"})

    transport = httpx.MockTransport(handler)
    client = HttpCloudClient(base_url="http://test-cloud", api_key="secret-key")
    client._client = httpx.AsyncClient(base_url="http://test-cloud", transport=transport)

    card_payload = CardsSyncPayload(cards=[
        CardSyncItem(barcode="1234567890123", balance=Decimal("10"), updated_at=datetime.now(UTC))
    ])

    # Cards bad json
    with pytest.raises(CloudProtocolError, match="CLOUD_PROTOCOL_ERROR"):
        await client.sync_cards(card_payload)

    # Cards missing required fields
    client._client.headers["X-Test-Route"] = "/cards/missing_fields"
    with pytest.raises(CloudProtocolError, match="CLOUD_PROTOCOL_ERROR"):
        await client.sync_cards(card_payload)

    # Transactions bad json
    tx_payload = TransactionsSyncPayload(transactions=[
        TransactionSyncItem(
            external_id="tx-1",
            barcode="1234567890123",
            type="accrual",
            amount=Decimal("10"),
            balance_after=Decimal("20"),
            occurred_at=datetime.now(UTC),
        )
    ])
    with pytest.raises(CloudProtocolError, match="CLOUD_PROTOCOL_ERROR"):
        await client.sync_transactions(tx_payload)

    # Heartbeat missing fields
    hb_payload = HeartbeatPayload(version="0.1.0")
    with pytest.raises(CloudProtocolError, match="CLOUD_PROTOCOL_ERROR"):
        await client.send_heartbeat(hb_payload)

    await client.close()
