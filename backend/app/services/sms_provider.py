"""SMS Provider abstraction layer and test fakes for SMS fallback auth."""
from typing import Protocol

from app.core.config import settings
from app.core.errors import AppError


class SmsProvider(Protocol):
    """Abstract SMS delivery provider interface."""

    async def send_otp(self, phone: str, code: str) -> None:
        """Send a one-time verification code to recipient phone number."""
        ...


class DisabledSmsProvider:
    """Default provider implementation when no external SMS vendor adapter is configured."""

    async def send_otp(self, phone: str, code: str) -> None:
        raise AppError(
            code="SMS_PROVIDER_NOT_CONFIGURED",
            message="SMS delivery is not configured on this server.",
            status_code=503,
        )


class FakeSmsProvider:
    """In-memory test fake to record sent OTP codes and simulate delivery failures."""

    def __init__(self) -> None:
        self.sent_messages: list[tuple[str, str]] = []
        self.fail_next: bool = False

    async def send_otp(self, phone: str, code: str) -> None:
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("Simulated SMS provider delivery failure")
        self.sent_messages.append((phone, code))

    def clear(self) -> None:
        self.sent_messages.clear()
        self.fail_next = False


_default_fake_provider: FakeSmsProvider | None = None


def get_fake_sms_provider() -> FakeSmsProvider:
    """Return singleton FakeSmsProvider for test inspection. Strictly forbidden outside APP_ENV=test."""
    if settings.app_env.lower() != "test":
        raise RuntimeError("FakeSmsProvider is strictly forbidden outside APP_ENV=test")
    global _default_fake_provider
    if _default_fake_provider is None:
        _default_fake_provider = FakeSmsProvider()
    return _default_fake_provider


def get_sms_provider() -> SmsProvider:
    """FastAPI dependency for resolving active SMS provider."""
    if settings.sms_provider_mode == "disabled":
        return DisabledSmsProvider()
    if settings.sms_provider_mode == "fake":
        if settings.app_env.lower() != "test":
            raise AppError(
                code="SMS_PROVIDER_NOT_CONFIGURED",
                message="SMS delivery is not configured on this server.",
                status_code=503,
            )
        return get_fake_sms_provider()
    return DisabledSmsProvider()
