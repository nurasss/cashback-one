"""Outbound push notifications (Firebase Cloud Messaging HTTP v1).

Direct integration with FCM HTTP v1 using Google Service Account OAuth2 JWT (RS256).
Does not require google-auth or firebase-admin dependencies.
"""
import json
import logging
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

import httpx
import jwt

from app.core.config import settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)

_DEFAULT_TOKEN_URI = "https://oauth2.googleapis.com/token"
_FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"


class PushStatus(str, Enum):
    DELIVERED = "delivered"
    INVALID_TOKEN = "invalid_token"
    REJECTED = "rejected"
    TEMPORARY_ERROR = "temporary_error"


@dataclass(frozen=True)
class PushResult:
    status: PushStatus
    error_details: str | None = None


class PushSender(Protocol):
    """Protocol for delivering push notifications."""

    disabled: bool

    async def send(
        self,
        token: str,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> PushResult: ...


def _not_configured() -> AppError:
    return AppError(
        code="PUSH_NOT_CONFIGURED",
        message="Push delivery is not configured on this server.",
        status_code=503,
    )


class DisabledPushSender:
    """Default sender when PUSH_PROVIDER_MODE is disabled."""

    disabled = True

    async def send(
        self,
        token: str,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> PushResult:
        raise _not_configured()


@dataclass(frozen=True)
class FakePushMessage:
    token: str
    title: str
    body: str
    data: dict[str, str] | None = None


class FakePushSender:
    """In-memory push sender for testing (APP_ENV=test only)."""

    disabled = False

    def __init__(self) -> None:
        self.sent_messages: list[FakePushMessage] = []
        self.results_by_token: dict[str, PushResult] = {}
        self.next_result: PushResult | None = None

    async def send(
        self,
        token: str,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> PushResult:
        self.sent_messages.append(FakePushMessage(token=token, title=title, body=body, data=data))
        if token in self.results_by_token:
            return self.results_by_token[token]
        if self.next_result is not None:
            res = self.next_result
            self.next_result = None
            return res
        return PushResult(status=PushStatus.DELIVERED)

    def clear(self) -> None:
        self.sent_messages.clear()
        self.results_by_token.clear()
        self.next_result = None


class LogPushSender:
    """Local development only: prints push summary to log without full data payload."""

    disabled = False

    async def send(
        self,
        token: str,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> PushResult:
        masked_token = f"...{token[-6:]}" if len(token) > 6 else "***"
        data_keys = list(data.keys()) if data else []
        logger.warning(
            "DEV Push notification to %s: title=%r body=%r data_keys=%s",
            masked_token,
            title,
            body,
            data_keys,
        )
        return PushResult(status=PushStatus.DELIVERED)


class FcmPushSender:
    """Firebase Cloud Messaging HTTP v1 push sender using service account OAuth2 token."""

    disabled = False

    def __init__(
        self,
        project_id: str,
        service_account_file: str,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not project_id.strip():
            raise ValueError("FCM_PROJECT_ID is required when PUSH_PROVIDER_MODE=fcm")
        if not service_account_file.strip():
            raise ValueError("FCM_SERVICE_ACCOUNT_FILE is required when PUSH_PROVIDER_MODE=fcm")

        sa_path = Path(service_account_file)
        if not sa_path.is_file():
            raise ValueError(f"FCM service account file not found: {service_account_file}")

        try:
            with sa_path.open("r", encoding="utf-8") as f:
                sa_data = json.load(f)
        except Exception as exc:
            raise ValueError(f"Failed to parse FCM service account JSON: {type(exc).__name__}") from exc

        if not isinstance(sa_data, dict):
            raise TypeError("FCM service account JSON must be an object")

        client_email = sa_data.get("client_email")
        private_key = sa_data.get("private_key")
        if not client_email or not private_key:
            raise ValueError("FCM service account JSON is missing client_email or private_key")

        self._project_id = project_id.strip()
        self._client_email = str(client_email).strip()
        self._private_key = str(private_key)
        self._private_key_id = str(sa_data.get("private_key_id") or "")
        self._token_uri = str(sa_data.get("token_uri") or _DEFAULT_TOKEN_URI).strip()
        self._timeout = timeout
        self._transport = transport

        self._cached_token: str | None = None
        self._token_expires_at: float = 0.0

    async def _get_access_token(self) -> str:
        now = time.time()
        if self._cached_token is not None and now + 60.0 < self._token_expires_at:
            return self._cached_token

        iat = int(now)
        exp = iat + 3600
        payload = {
            "iss": self._client_email,
            "sub": self._client_email,
            "aud": self._token_uri,
            "iat": iat,
            "exp": exp,
            "scope": _FCM_SCOPE,
        }
        headers: dict[str, Any] = {}
        if self._private_key_id:
            headers["kid"] = self._private_key_id

        try:
            signed_jwt = jwt.encode(
                payload,
                self._private_key,
                algorithm="RS256",
                headers=headers,
            )
        except Exception as exc:
            logger.error("Failed to sign FCM OAuth2 JWT assertion: %s", type(exc).__name__)
            raise

        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            resp = await client.post(
                self._token_uri,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": signed_jwt,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        if resp.status_code != 200:
            logger.warning("FCM OAuth2 token request rejected: status=%s", resp.status_code)
            raise RuntimeError(f"FCM OAuth2 token request rejected with HTTP {resp.status_code}")

        token_data = resp.json()
        access_token = str(token_data["access_token"])
        expires_in = int(token_data.get("expires_in", 3600))

        self._cached_token = access_token
        self._token_expires_at = now + max(60.0, float(expires_in) - 120.0)
        return access_token

    async def send(
        self,
        token: str,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> PushResult:
        try:
            access_token = await self._get_access_token()
        except Exception as exc:  # noqa: BLE001 - return PushResult on token errors
            logger.warning("FCM token retrieval error: %s", type(exc).__name__)
            return PushResult(
                status=PushStatus.TEMPORARY_ERROR,
                error_details=f"OAUTH_TOKEN_ERROR: {type(exc).__name__}",
            )

        fcm_message: dict[str, Any] = {
            "token": token,
            "notification": {
                "title": title,
                "body": body,
            },
            "android": {
                "priority": "HIGH",
                "notification": {
                    "channel_id": "default",
                },
            },
        }
        if data:
            fcm_message["data"] = {str(k): str(v) for k, v in data.items()}

        url = f"https://fcm.googleapis.com/v1/projects/{self._project_id}/messages:send"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                response = await client.post(url, json={"message": fcm_message}, headers=headers)
        except httpx.HTTPError as exc:
            logger.warning("FCM HTTP transport error: %s", type(exc).__name__)
            return PushResult(
                status=PushStatus.TEMPORARY_ERROR,
                error_details=f"TRANSPORT_ERROR: {type(exc).__name__}",
            )

        if response.status_code == 200:
            return PushResult(status=PushStatus.DELIVERED)

        # Parse FCM error
        error_code = ""
        status_str = ""
        message_str = ""
        try:
            err_json = response.json().get("error", {})
            status_str = str(err_json.get("status", "")).upper()
            message_str = str(err_json.get("message", ""))
            for item in err_json.get("details", []):
                if isinstance(item, dict) and "errorCode" in item:
                    error_code = str(item["errorCode"]).upper()
                    break
        except (ValueError, KeyError, TypeError) as exc:
            logger.debug("Failed to parse FCM error response JSON: %s", exc)

        # 1. Unregistered token (FCM explicitly returns errorCode UNREGISTERED)
        if error_code == "UNREGISTERED":
            return PushResult(status=PushStatus.INVALID_TOKEN, error_details="UNREGISTERED")

        # 2. Invalid argument: distinguish token-related error from payload-related error
        if error_code == "INVALID_ARGUMENT" or status_str == "INVALID_ARGUMENT":
            lower_msg = message_str.lower()
            if "registration token" in lower_msg or "invalid token" in lower_msg:
                return PushResult(status=PushStatus.INVALID_TOKEN, error_details="INVALID_ARGUMENT_TOKEN")
            logger.warning("FCM request rejected with INVALID_ARGUMENT (non-token error)")
            return PushResult(status=PushStatus.REJECTED, error_details="INVALID_ARGUMENT_PAYLOAD")

        # 3. NOT_FOUND without UNREGISTERED: could be missing project or endpoint URL error
        if status_str == "NOT_FOUND" or response.status_code == 404:
            logger.warning("FCM endpoint returned HTTP 404 NOT_FOUND without UNREGISTERED code")
            return PushResult(status=PushStatus.TEMPORARY_ERROR, error_details="HTTP_404_NOT_FOUND")

        return PushResult(
            status=PushStatus.TEMPORARY_ERROR,
            error_details=f"HTTP_{response.status_code}_{status_str or error_code}",
        )


_fake_push_sender: FakePushSender | None = None


def get_fake_push_sender() -> FakePushSender:
    if settings.app_env != "test":
        raise RuntimeError("FakePushSender is strictly forbidden outside APP_ENV=test")
    global _fake_push_sender
    if _fake_push_sender is None:
        _fake_push_sender = FakePushSender()
    return _fake_push_sender


def get_push_sender() -> PushSender:
    """FastAPI dependency resolving configured PushSender."""
    mode = settings.push_provider_mode
    if mode == "fcm":
        return FcmPushSender(
            project_id=settings.fcm_project_id,
            service_account_file=settings.fcm_service_account_file,
            timeout=settings.push_send_timeout_seconds,
        )
    if mode == "log" and settings.app_env != "production":
        return LogPushSender()
    if mode == "fake" and settings.app_env == "test":
        return get_fake_push_sender()
    return DisabledPushSender()
