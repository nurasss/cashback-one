"""Outbound WhatsApp messages (login OTP, POS redemption codes).

Wappi send API contract (docs/WAPPI_SEND_CONTRACT.md):
    POST {WAPPI_API_BASE_URL}/api/sync/message/send?profile_id={profile}
    Authorization: {WAPPI_API_TOKEN}
    {"recipient": "77001234567", "body": "..."}
Status: NOT VERIFIED against a live Wappi profile.
"""
import logging
from typing import Protocol

import httpx

from app.core.config import settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)


class WhatsAppSender(Protocol):
    """Delivers a plain-text WhatsApp message to an E.164 phone number."""

    disabled: bool

    async def send_text(self, phone: str, text: str) -> None: ...


def _not_configured() -> AppError:
    return AppError(
        code="WHATSAPP_NOT_CONFIGURED",
        message="WhatsApp delivery is not configured on this server.",
        status_code=503,
    )


def _delivery_failed() -> AppError:
    return AppError(
        code="WHATSAPP_DELIVERY_UNAVAILABLE",
        message="WhatsApp message could not be delivered. Please try again later.",
        status_code=503,
    )


class DisabledWhatsAppSender:
    disabled = True

    async def send_text(self, phone: str, text: str) -> None:
        raise _not_configured()


class FakeWhatsAppSender:
    """In-memory sender for tests: records messages and can simulate a failure."""

    disabled = False

    def __init__(self) -> None:
        self.sent_messages: list[tuple[str, str]] = []
        self.fail_next = False

    async def send_text(self, phone: str, text: str) -> None:
        if self.fail_next:
            self.fail_next = False
            raise _delivery_failed()
        self.sent_messages.append((phone, text))

    def clear(self) -> None:
        self.sent_messages.clear()
        self.fail_next = False


class WappiWhatsAppSender:
    disabled = False

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    async def send_text(self, phone: str, text: str) -> None:
        profile_id = settings.wappi_sender_profile_id or settings.wappi_login_profile_id
        url = f"{settings.wappi_api_base_url.rstrip('/')}/api/sync/message/send"
        try:
            async with httpx.AsyncClient(
                timeout=settings.wappi_send_timeout_seconds, transport=self._transport
            ) as client:
                response = await client.post(
                    url,
                    params={"profile_id": profile_id},
                    headers={"Authorization": settings.wappi_api_token},
                    json={"recipient": phone.lstrip("+"), "body": text},
                )
        except httpx.HTTPError as exc:
            # Never log the recipient or the message: both contain PII / one-time codes.
            logger.warning("Wappi send failed: %s", type(exc).__name__)
            raise _delivery_failed() from exc
        if response.status_code >= 400:
            logger.warning("Wappi send rejected with HTTP %s", response.status_code)
            raise _delivery_failed()


class LogWhatsAppSender:
    """Local development only: prints the message (including one-time codes) to the server log."""

    disabled = False

    async def send_text(self, phone: str, text: str) -> None:
        logger.warning("DEV WhatsApp message to %s: %s", phone, text.replace("\n", " "))


_fake_sender: FakeWhatsAppSender | None = None


def get_fake_whatsapp_sender() -> FakeWhatsAppSender:
    if settings.app_env != "test":
        raise RuntimeError("FakeWhatsAppSender is strictly forbidden outside APP_ENV=test")
    global _fake_sender
    if _fake_sender is None:
        _fake_sender = FakeWhatsAppSender()
    return _fake_sender


def get_whatsapp_sender() -> WhatsAppSender:
    """FastAPI dependency resolving the configured WhatsApp sender."""
    mode = settings.whatsapp_provider_mode
    if mode == "wappi":
        return WappiWhatsAppSender()
    if mode == "log" and settings.app_env != "production":
        return LogWhatsAppSender()
    if mode == "fake" and settings.app_env == "test":
        return get_fake_whatsapp_sender()
    return DisabledWhatsAppSender()


class WhatsAppOtpProvider:
    """Adapts a WhatsApp sender to the OTP provider interface used by the OTP service."""

    def __init__(self, sender: WhatsAppSender) -> None:
        self.sender = sender
        self.disabled = sender.disabled

    async def send_otp(self, phone: str, code: str) -> None:
        await self.sender.send_text(
            phone,
            f"Код для входа в приложение: {code}\n"
            "Никому не сообщайте этот код, даже сотрудникам магазина.",
        )
