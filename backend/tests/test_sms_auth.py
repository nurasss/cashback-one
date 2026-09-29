import re
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    generate_sms_otp,
    hash_sms_otp,
    verify_sms_otp_hash,
)
from app.core.time import utcnow
from app.models.entities import AuthSession, OtpCode, User
from app.services.rate_limiter import _test_limiter
from app.services.sms_auth_service import phone_fingerprint
from app.services.sms_provider import get_fake_sms_provider


@pytest.fixture(autouse=True)
def reset_test_state() -> None:
    """Reset rate limiter and fake SMS provider before each test."""
    _test_limiter.reset()
    fake_provider = get_fake_sms_provider()
    fake_provider.clear()


def test_sms_otp_generator() -> None:
    """generate_sms_otp must return exactly 6 digits using secrets."""
    codes = set()
    for _ in range(50):
        code = generate_sms_otp()
        assert len(code) == 6
        assert re.fullmatch(r"^\d{6}$", code) is not None
        codes.add(code)
    assert len(codes) > 1


def test_sms_otp_hash_and_verify() -> None:
    """HMAC-SHA256 must be deterministic, bound to phone, and verified constant-time."""
    phone = "+77011234567"
    otp = "123456"
    digest = hash_sms_otp(phone, otp)
    assert len(digest) == 64
    assert digest == hash_sms_otp(phone, otp)
    assert verify_sms_otp_hash(phone, otp, digest) is True
    # Different phone fails
    assert verify_sms_otp_hash("+77017654321", otp, digest) is False
    # Different OTP fails
    assert verify_sms_otp_hash(phone, "654321", digest) is False
    # Whitespace normalized
    assert verify_sms_otp_hash(f" {phone} ", f" {otp} ", digest) is True


def test_phone_fingerprint() -> None:
    """phone_fingerprint returns 32-char hex and does not leak raw phone."""
    phone = "+77011234567"
    fp = phone_fingerprint(phone)
    assert len(fp) == 32
    assert phone not in fp
    assert fp == phone_fingerprint(" +77011234567 ")


@pytest.mark.asyncio
async def test_sms_request_disabled_provider_returns_503(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When SMS_PROVIDER_MODE=disabled, /auth/sms/request returns 503 and rolls back DB."""
    monkeypatch.setattr(settings, "sms_provider_mode", "disabled")
    phone = "+77011234567"
    device_id = "dev-disabled-1"

    response = await client.post(
        "/auth/sms/request",
        json={"phone": phone, "device_id": device_id},
    )
    assert response.status_code == 503
    data = response.json()
    assert data["error"]["code"] == "SMS_PROVIDER_NOT_CONFIGURED"

    # Verify no OtpCode record persisted
    records = (
        await db_session.execute(
            select(OtpCode).where(OtpCode.phone == phone, OtpCode.device_id == device_id)
        )
    ).scalars().all()
    assert len(records) == 0


@pytest.mark.asyncio
async def test_sms_request_provider_failure_atomically_rolls_back(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When provider delivery fails, returns 503 SMS_DELIVERY_UNAVAILABLE and creates no OTP."""
    monkeypatch.setattr(settings, "sms_provider_mode", "fake")
    fake_provider = get_fake_sms_provider()
    fake_provider.fail_next = True

    phone = "+77011234567"
    device_id = "dev-fail-1"

    response = await client.post(
        "/auth/sms/request",
        json={"phone": phone, "device_id": device_id},
    )
    assert response.status_code == 503
    data = response.json()
    assert data["error"]["code"] == "SMS_DELIVERY_UNAVAILABLE"

    # Verify no OtpCode record persisted
    records = (
        await db_session.execute(
            select(OtpCode).where(OtpCode.phone == phone, OtpCode.device_id == device_id)
        )
    ).scalars().all()
    assert len(records) == 0


@pytest.mark.asyncio
async def test_sms_request_success_with_fake_provider(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST /auth/sms/request creates pending OTP, delivers via fake, does not store plaintext."""
    monkeypatch.setattr(settings, "sms_provider_mode", "fake")
    fake_provider = get_fake_sms_provider()

    phone = "+77011234567"
    device_id = "dev-success-1"

    response = await client.post(
        "/auth/sms/request",
        json={"phone": phone, "device_id": device_id},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "sent"
    assert data["expires_in"] == settings.sms_otp_ttl_seconds

    # Fake provider received the code
    assert len(fake_provider.sent_messages) == 1
    sent_phone, sent_code = fake_provider.sent_messages[0]
    assert sent_phone == phone
    assert len(sent_code) == 6

    # Verify database record
    otp_record = (
        await db_session.execute(
            select(OtpCode).where(OtpCode.phone == phone, OtpCode.device_id == device_id)
        )
    ).scalar_one()
    assert otp_record.status == "pending"
    assert otp_record.attempts == 0
    assert otp_record.verified_at is None
    # Code hash is 64 hex characters HMAC, NEVER plaintext OTP
    assert len(otp_record.code_hash) == 64
    assert otp_record.code_hash != sent_code
    assert verify_sms_otp_hash(phone, sent_code, otp_record.code_hash) is True


@pytest.mark.asyncio
async def test_sms_request_supersedes_previous_pending(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Repeated request for same (phone, device) supersedes previous pending OTP."""
    monkeypatch.setattr(settings, "sms_provider_mode", "fake")
    fake_provider = get_fake_sms_provider()

    phone = "+77011234567"
    device_id = "dev-supersede-1"

    # Request 1
    r1 = await client.post("/auth/sms/request", json={"phone": phone, "device_id": device_id})
    assert r1.status_code == 200
    code1 = fake_provider.sent_messages[0][1]

    # Request 2
    r2 = await client.post("/auth/sms/request", json={"phone": phone, "device_id": device_id})
    assert r2.status_code == 200
    code2 = fake_provider.sent_messages[1][1]

    # In DB, there should be 1 superseded and 1 pending
    records = (
        await db_session.execute(
            select(OtpCode)
            .where(OtpCode.phone == phone, OtpCode.device_id == device_id)
            .order_by(OtpCode.created_at.asc())
        )
    ).scalars().all()
    assert len(records) == 2
    assert records[0].status == "superseded"
    assert records[1].status == "pending"

    # Verifying code1 should now fail as not found / not pending
    v1 = await client.post(
        "/auth/sms/verify",
        json={"phone": phone, "device_id": device_id, "code": code1},
    )
    assert v1.status_code == 400
    # Verifying code2 succeeds
    v2 = await client.post(
        "/auth/sms/verify",
        json={"phone": phone, "device_id": device_id, "code": code2},
    )
    assert v2.status_code == 200


@pytest.mark.asyncio
async def test_sms_request_rate_limiting(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rate limits on phone, device_id, and IP must be enforced."""
    monkeypatch.setattr(settings, "sms_provider_mode", "fake")
    monkeypatch.setattr(settings, "sms_otp_request_phone_limit", 2)
    monkeypatch.setattr(settings, "sms_otp_request_device_limit", 2)

    phone = "+77019998877"
    dev1 = "dev-rate-1"

    # Attempt 1 & 2 succeed
    res1 = await client.post("/auth/sms/request", json={"phone": phone, "device_id": dev1})
    assert res1.status_code == 200
    res2 = await client.post("/auth/sms/request", json={"phone": phone, "device_id": dev1})
    assert res2.status_code == 200

    # Attempt 3 fails with 429
    res3 = await client.post("/auth/sms/request", json={"phone": phone, "device_id": dev1})
    assert res3.status_code == 429
    assert res3.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_sms_verify_success_flow(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify correct OTP creates User, AuthSession, returns TokenResponse and consumes OTP."""
    monkeypatch.setattr(settings, "sms_provider_mode", "fake")
    fake_provider = get_fake_sms_provider()

    phone = "+77015554433"
    device_id = "dev-verify-flow-1"

    req_res = await client.post("/auth/sms/request", json={"phone": phone, "device_id": device_id})
    assert req_res.status_code == 200
    code = fake_provider.sent_messages[0][1]

    verify_res = await client.post(
        "/auth/sms/verify",
        json={"phone": phone, "device_id": device_id, "code": code},
    )
    assert verify_res.status_code == 200
    token_data = verify_res.json()
    assert "access_token" in token_data
    assert "refresh_token" in token_data
    assert token_data["token_type"] == "bearer"
    assert token_data["expires_in"] == settings.access_token_ttl_seconds

    # OtpCode status is consumed and verified_at is set
    otp = (
        await db_session.execute(
            select(OtpCode).where(OtpCode.phone == phone, OtpCode.device_id == device_id)
        )
    ).scalar_one()
    assert otp.status == "consumed"
    assert otp.verified_at is not None

    # User exists
    user = (await db_session.execute(select(User).where(User.phone == phone))).scalar_one()
    assert user is not None

    # AuthSession exists and is linked
    auth_session = (
        await db_session.execute(
            select(AuthSession).where(AuthSession.user_id == user.id, AuthSession.device_id == device_id)
        )
    ).scalar_one()
    assert auth_session is not None
    assert auth_session.revoked_at is None


@pytest.mark.asyncio
async def test_sms_verify_single_use(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Consumed OTP cannot be reused."""
    monkeypatch.setattr(settings, "sms_provider_mode", "fake")
    fake_provider = get_fake_sms_provider()

    phone = "+77015554422"
    device_id = "dev-single-use"

    await client.post("/auth/sms/request", json={"phone": phone, "device_id": device_id})
    code = fake_provider.sent_messages[0][1]

    v1 = await client.post("/auth/sms/verify", json={"phone": phone, "device_id": device_id, "code": code})
    assert v1.status_code == 200

    v2 = await client.post("/auth/sms/verify", json={"phone": phone, "device_id": device_id, "code": code})
    assert v2.status_code == 400
    assert v2.json()["error"]["code"] == "OTP_NOT_FOUND"


@pytest.mark.asyncio
async def test_sms_verify_max_attempts_exhaustion(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """5 incorrect attempts exhaust the OTP and prevent further verification."""
    monkeypatch.setattr(settings, "sms_provider_mode", "fake")
    fake_provider = get_fake_sms_provider()

    phone = "+77015554411"
    device_id = "dev-max-att"

    await client.post("/auth/sms/request", json={"phone": phone, "device_id": device_id})
    correct_code = fake_provider.sent_messages[0][1]
    wrong_code = "999999" if correct_code != "999999" else "888888"

    # 4 wrong attempts return INVALID_CODE
    for _ in range(4):
        res = await client.post(
            "/auth/sms/verify",
            json={"phone": phone, "device_id": device_id, "code": wrong_code},
        )
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "INVALID_CODE"

    # 5th wrong attempt exhausts the code
    res5 = await client.post(
        "/auth/sms/verify",
        json={"phone": phone, "device_id": device_id, "code": wrong_code},
    )
    assert res5.status_code == 400
    assert res5.json()["error"]["code"] == "OTP_MAX_ATTEMPTS_EXCEEDED"

    # DB record is marked exhausted with attempts=5
    otp = (
        await db_session.execute(
            select(OtpCode).where(OtpCode.phone == phone, OtpCode.device_id == device_id)
        )
    ).scalar_one()
    assert otp.status == "exhausted"
    assert otp.attempts == 5

    # Subsequent attempt even with CORRECT code is rejected
    res_correct = await client.post(
        "/auth/sms/verify",
        json={"phone": phone, "device_id": device_id, "code": correct_code},
    )
    assert res_correct.status_code == 400
    assert res_correct.json()["error"]["code"] == "OTP_NOT_FOUND"


@pytest.mark.asyncio
async def test_sms_verify_expired_code(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Expired OTP returns 400 OTP_EXPIRED and transitions status to expired."""
    monkeypatch.setattr(settings, "sms_provider_mode", "fake")
    fake_provider = get_fake_sms_provider()

    phone = "+77015554400"
    device_id = "dev-expired-1"

    await client.post("/auth/sms/request", json={"phone": phone, "device_id": device_id})
    code = fake_provider.sent_messages[0][1]

    # Force expiration in DB
    otp = (
        await db_session.execute(
            select(OtpCode).where(OtpCode.phone == phone, OtpCode.device_id == device_id)
        )
    ).scalar_one()
    otp.expires_at = utcnow() - timedelta(seconds=10)
    await db_session.commit()

    res = await client.post(
        "/auth/sms/verify",
        json={"phone": phone, "device_id": device_id, "code": code},
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "OTP_EXPIRED"

    await db_session.refresh(otp)
    assert otp.status == "expired"


@pytest.mark.asyncio
async def test_sms_verify_device_mismatch(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifying with a different device_id than requested fails with OTP_NOT_FOUND."""
    monkeypatch.setattr(settings, "sms_provider_mode", "fake")
    fake_provider = get_fake_sms_provider()

    phone = "+77015554499"
    dev_a = "dev-alpha"
    dev_b = "dev-beta"

    await client.post("/auth/sms/request", json={"phone": phone, "device_id": dev_a})
    code = fake_provider.sent_messages[0][1]

    res = await client.post(
        "/auth/sms/verify",
        json={"phone": phone, "device_id": dev_b, "code": code},
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "OTP_NOT_FOUND"


@pytest.mark.asyncio
async def test_sms_schema_validation_rejections(client: AsyncClient) -> None:
    """Verify schema edge cases: bad phones, invalid device IDs, non-6-digit codes."""
    # Bad phones
    for bad_phone in ["12345", "not-a-phone", "+7abc1234567"]:
        r = await client.post("/auth/sms/request", json={"phone": bad_phone, "device_id": "d1"})
        assert r.status_code == 422

    # Blank / whitespace device
    for bad_dev in ["", "   "]:
        r = await client.post("/auth/sms/request", json={"phone": "+77011234567", "device_id": bad_dev})
        assert r.status_code == 422

    # Overly long device (>128 chars)
    r = await client.post(
        "/auth/sms/request",
        json={"phone": "+77011234567", "device_id": "x" * 129},
    )
    assert r.status_code == 422

    # Bad verify codes (letters, too short, too long)
    for bad_code in ["12345", "1234567", "abcdef", "12a456"]:
        r = await client.post(
            "/auth/sms/verify",
            json={"phone": "+77011234567", "device_id": "d1", "code": bad_code},
        )
        assert r.status_code == 422
