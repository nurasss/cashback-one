"""Cloud API client for POSCENTER Loyalty synchronization and heartbeat."""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

import httpx

from poscenter_loyalty_agent.models import (
    CardsSyncPayload,
    CardsSyncResult,
    HeartbeatPayload,
    HeartbeatResult,
    TransactionsSyncPayload,
    TransactionsSyncResult,
)

logger = logging.getLogger(__name__)

CARDS_SYNC_PATH = "/agent/sync/cards"
TRANSACTIONS_SYNC_PATH = "/agent/sync/transactions"
HEARTBEAT_PATH = "/agent/heartbeat"


class CloudClientError(Exception):
    """Base exception for Cloud API communication failures."""


class CloudRetryableError(CloudClientError):
    """Transient error that should be retried with exponential backoff (e.g. 5xx, timeout, 429)."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class CloudProtocolError(CloudRetryableError):
    """Raised when Cloud API returns a 2xx response with invalid JSON or malformed schema."""

    def __init__(self, message: str = "CLOUD_PROTOCOL_ERROR: Invalid or malformed 2xx response from Cloud API.") -> None:
        super().__init__(message)
        self.code = "CLOUD_PROTOCOL_ERROR"


class CloudNonRetryableError(CloudClientError):
    """Fatal or client-side error that must NOT be retried (e.g. 401, 403, 422)."""


class CloudAuthError(CloudNonRetryableError):
    """Authentication or authorization failure (401/403)."""


@runtime_checkable
class CloudClient(Protocol):
    """Protocol for Cloud API communications."""

    async def sync_cards(self, payload: CardsSyncPayload) -> CardsSyncResult:
        ...

    async def sync_transactions(self, payload: TransactionsSyncPayload) -> TransactionsSyncResult:
        ...

    async def send_heartbeat(self, payload: HeartbeatPayload) -> HeartbeatResult:
        ...

    async def close(self) -> None:
        ...


class HttpCloudClient:
    """Production HTTP client for the POSCENTER Loyalty Cloud API using httpx."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 30.0,
        verify_ssl: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {
                "X-Agent-Key": self.api_key,
                "Content-Type": "application/json",
                "User-Agent": "POSCENTER-Loyalty-Agent/0.1.0",
            }
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=httpx.Timeout(self.timeout),
                verify=self.verify_ssl,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _handle_response_error(self, response: httpx.Response) -> None:
        status = response.status_code
        if status in (401, 403):
            raise CloudAuthError(f"Cloud API authentication failed ({status})")
        if status == 429:
            retry_after_hdr = response.headers.get("Retry-After")
            retry_after = float(retry_after_hdr) if retry_after_hdr and retry_after_hdr.isdigit() else None
            raise CloudRetryableError("Cloud API rate limited (429)", retry_after=retry_after)
        if 400 <= status < 500:
            raise CloudNonRetryableError(f"Cloud API rejected request ({status})")
        if status >= 500:
            raise CloudRetryableError(f"Cloud API server error ({status})")

    async def sync_cards(self, payload: CardsSyncPayload) -> CardsSyncResult:
        client = self._get_client()
        try:
            resp = await client.post(
                CARDS_SYNC_PATH,
                json=payload.model_dump(mode="json"),
            )
        except (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError) as exc:
            raise CloudRetryableError(f"Network error while syncing cards: {exc}") from exc
        except Exception as exc:
            raise CloudNonRetryableError(f"Unexpected error while sending cards: {exc}") from exc

        if resp.is_error:
            self._handle_response_error(resp)

        try:
            body = resp.json()
            return CardsSyncResult.model_validate(body)
        except Exception as exc:
            raise CloudProtocolError(
                f"CLOUD_PROTOCOL_ERROR: Failed parsing Cloud 2xx cards response: {type(exc).__name__}"
            ) from None

    async def sync_transactions(self, payload: TransactionsSyncPayload) -> TransactionsSyncResult:
        client = self._get_client()
        try:
            resp = await client.post(
                TRANSACTIONS_SYNC_PATH,
                json=payload.model_dump(mode="json"),
            )
        except (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError) as exc:
            raise CloudRetryableError(f"Network error while syncing transactions: {exc}") from exc
        except Exception as exc:
            raise CloudNonRetryableError(f"Unexpected error while sending transactions: {exc}") from exc

        if resp.is_error:
            self._handle_response_error(resp)

        try:
            body = resp.json()
            return TransactionsSyncResult.model_validate(body)
        except Exception as exc:
            raise CloudProtocolError(
                f"CLOUD_PROTOCOL_ERROR: Failed parsing Cloud 2xx transactions response: {type(exc).__name__}"
            ) from None

    async def send_heartbeat(self, payload: HeartbeatPayload) -> HeartbeatResult:
        client = self._get_client()
        try:
            resp = await client.post(
                HEARTBEAT_PATH,
                json=payload.model_dump(mode="json"),
            )
        except (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError) as exc:
            raise CloudRetryableError(f"Network error while sending heartbeat: {exc}") from exc
        except Exception as exc:
            raise CloudNonRetryableError(f"Unexpected error while sending heartbeat: {exc}") from exc

        if resp.is_error:
            self._handle_response_error(resp)

        try:
            body = resp.json()
            return HeartbeatResult.model_validate(body)
        except Exception as exc:
            raise CloudProtocolError(
                f"CLOUD_PROTOCOL_ERROR: Failed parsing Cloud 2xx heartbeat response: {type(exc).__name__}"
            ) from None


class FakeCloudClient:
    """Deterministic in-memory CloudClient for testing without network calls."""

    def __init__(self) -> None:
        self.synced_cards: list[CardsSyncPayload] = []
        self.synced_transactions: list[TransactionsSyncPayload] = []
        self.heartbeats: list[HeartbeatPayload] = []
        self.next_cards_error: Exception | None = None
        self.next_transactions_error: Exception | None = None
        self.next_heartbeat_error: Exception | None = None
        self.is_closed = False

    async def sync_cards(self, payload: CardsSyncPayload) -> CardsSyncResult:
        if self.next_cards_error:
            err = self.next_cards_error
            self.next_cards_error = None
            raise err
        self.synced_cards.append(payload)
        return CardsSyncResult(
            received=len(payload.cards),
            created=len(payload.cards),
            updated=0,
            ignored_stale=0,
        )

    async def sync_transactions(self, payload: TransactionsSyncPayload) -> TransactionsSyncResult:
        if self.next_transactions_error:
            err = self.next_transactions_error
            self.next_transactions_error = None
            raise err
        self.synced_transactions.append(payload)
        return TransactionsSyncResult(
            received=len(payload.transactions),
            created=len(payload.transactions),
            duplicates=0,
        )

    async def send_heartbeat(self, payload: HeartbeatPayload) -> HeartbeatResult:
        if self.next_heartbeat_error:
            err = self.next_heartbeat_error
            self.next_heartbeat_error = None
            raise err
        self.heartbeats.append(payload)
        return HeartbeatResult(status="ok")

    async def close(self) -> None:
        self.is_closed = True
