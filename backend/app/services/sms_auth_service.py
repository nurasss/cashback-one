"""Domain service for SMS fallback authentication: requesting OTP and verification."""
import hashlib
import logging
import uuid
from datetime import timedelta

from sqlalchemy import select, text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    generate_sms_otp,
    hash_refresh_token,
    hash_sms_otp,
    verify_sms_otp_hash,
)
from app.core.time import as_utc, utcnow
from app.models.entities import AuthSession, OtpCode
from app.schemas.auth import SmsOtpRequestResponse, TokenResponse
from app.services.rate_limiter import RateLimiter
from app.services.sms_provider import DisabledSmsProvider, SmsProvider
from app.services.user_service import get_or_create_user_by_phone

logger = logging.getLogger(__name__)


def phone_fingerprint(phone: str) -> str:
    """Compute non-reversible SHA-256 fingerprint of phone for rate-limiting keys."""
    return hashlib.sha256(f"phone:{phone.strip()}".encode()).hexdigest()[:32]


async def request_sms_otp(
    session: AsyncSession,
    phone: str,
    device_id: str,
    client_ip: str,
    limiter: RateLimiter,
    sms_provider: SmsProvider,
) -> SmsOtpRequestResponse:
    """Request a 6-digit SMS OTP for fallback customer login.

    Invariants:
    1. Provider readiness checked before rate limiting; disabled provider does not consume quota.
    2. Rate limits enforced on phone (fingerprint), device_id, and client_ip.
    3. Any existing pending OTP for (phone, device_id) is invalidated (superseded).
    4. 6-digit cryptographically secure code generated; plaintext never saved to DB or logged.
    5. Code sent via SmsProvider before committing; failure triggers atomic rollback so no
       orphaned active OTP remains in DB.
    """
    if isinstance(sms_provider, DisabledSmsProvider):
        raise AppError(
            code="SMS_PROVIDER_NOT_CONFIGURED",
            message="SMS delivery is not configured on this server.",
            status_code=503,
        )

    clean_phone = phone.strip()
    clean_device_id = device_id.strip()

    # Rate limiting
    ph_fp = phone_fingerprint(clean_phone)
    if await limiter.is_rate_limited(
        f"sms:ph:{ph_fp}",
        settings.sms_otp_request_phone_limit,
        settings.sms_otp_rate_window_seconds,
    ):
        raise AppError(
            code="RATE_LIMIT_EXCEEDED",
            message="Too many SMS requests for this phone number. Please try again later.",
            status_code=429,
        )

    if await limiter.is_rate_limited(
        f"sms:dev:{clean_device_id}",
        settings.sms_otp_request_device_limit,
        settings.sms_otp_rate_window_seconds,
    ):
        raise AppError(
            code="RATE_LIMIT_EXCEEDED",
            message="Too many SMS requests from this device. Please try again later.",
            status_code=429,
        )

    if await limiter.is_rate_limited(
        f"sms:ip:{client_ip}",
        settings.sms_otp_request_ip_limit,
        settings.sms_otp_rate_window_seconds,
    ):
        raise AppError(
            code="RATE_LIMIT_EXCEEDED",
            message="Too many SMS requests from this IP. Please try again later.",
            status_code=429,
        )

    # Concurrency protection: serialize OTP creation per (phone, device_id) on PostgreSQL
    try:
        bind = session.get_bind()
        dialect_name = bind.dialect.name if bind else ""
    except (AttributeError, SQLAlchemyError):
        dialect_name = ""

    if dialect_name == "postgresql":
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:k1), hashtext(:k2))"),
            {"k1": clean_phone, "k2": clean_device_id},
        )

    # Invalidate previous pending OTPs for this phone + device
    await session.execute(
        update(OtpCode)
        .where(
            OtpCode.phone == clean_phone,
            OtpCode.device_id == clean_device_id,
            OtpCode.status == "pending",
        )
        .values(status="superseded")
    )

    # Generate 6-digit OTP and HMAC digest
    plain_otp = generate_sms_otp()
    code_hash = hash_sms_otp(clean_phone, plain_otp)
    now = utcnow()
    expires_at = now + timedelta(seconds=settings.sms_otp_ttl_seconds)

    otp_record = OtpCode(
        id=uuid.uuid4(),
        phone=clean_phone,
        device_id=clean_device_id,
        code_hash=code_hash,
        expires_at=expires_at,
        attempts=0,
        status="pending",
        created_at=now,
        verified_at=None,
    )
    session.add(otp_record)

    # Provider delivery with atomic rollback on failure
    try:
        await sms_provider.send_otp(clean_phone, plain_otp)
    except AppError:
        await session.rollback()
        raise
    except Exception as exc:
        await session.rollback()
        logger.warning("SMS delivery failed: %s", type(exc).__name__)
        raise AppError(
            code="SMS_DELIVERY_UNAVAILABLE",
            message="SMS delivery is currently unavailable. Please try again later.",
            status_code=503,
        ) from exc

    await session.commit()
    return SmsOtpRequestResponse(status="sent", expires_in=settings.sms_otp_ttl_seconds)


async def verify_sms_otp(
    session: AsyncSession,
    phone: str,
    device_id: str,
    code: str,
) -> TokenResponse:
    """Verify 6-digit SMS OTP, consume it, and issue access and refresh tokens.

    Invariants:
    1. Locked with FOR UPDATE to prevent race conditions on attempt counters.
    2. Maximum 5 attempts allowed. Exhausted codes are immediately marked unusable.
    3. Expired codes are rejected and cannot be verified.
    4. Successful verification is single-use; marks code as consumed.
    5. Concurrent correct verifications: exactly one succeeds and issues session.
    """
    clean_phone = phone.strip()
    clean_device_id = device_id.strip()
    clean_code = code.strip()
    now = utcnow()

    # Query with row lock
    stmt = (
        select(OtpCode)
        .where(
            OtpCode.phone == clean_phone,
            OtpCode.device_id == clean_device_id,
            OtpCode.status == "pending",
        )
        .order_by(OtpCode.created_at.desc())
        .limit(1)
        .with_for_update()
    )
    otp_record = (await session.execute(stmt)).scalar_one_or_none()

    if otp_record is None:
        raise AppError(
            code="OTP_NOT_FOUND",
            message="No active verification code found for this phone and device.",
            status_code=400,
        )

    # Check expiration
    if as_utc(otp_record.expires_at) <= now:
        otp_record.status = "expired"
        await session.commit()
        raise AppError(
            code="OTP_EXPIRED",
            message="Verification code has expired. Please request a new one.",
            status_code=400,
        )

    # Check attempt threshold
    if otp_record.attempts >= settings.sms_otp_max_attempts:
        otp_record.status = "exhausted"
        await session.commit()
        raise AppError(
            code="OTP_MAX_ATTEMPTS_EXCEEDED",
            message="Too many incorrect attempts. Please request a new code.",
            status_code=400,
        )

    # Verify cryptographic HMAC
    if not verify_sms_otp_hash(clean_phone, clean_code, otp_record.code_hash):
        otp_record.attempts += 1
        if otp_record.attempts >= settings.sms_otp_max_attempts:
            otp_record.status = "exhausted"
            await session.commit()
            raise AppError(
                code="OTP_MAX_ATTEMPTS_EXCEEDED",
                message="Too many incorrect attempts. Please request a new code.",
                status_code=400,
            )
        await session.commit()
        raise AppError(
            code="INVALID_CODE",
            message="Invalid verification code.",
            status_code=400,
        )

    # Code is valid: mark consumed
    otp_record.status = "consumed"
    otp_record.verified_at = now

    user = await get_or_create_user_by_phone(session, clean_phone)

    raw_refresh = generate_refresh_token()
    refresh_hash = hash_refresh_token(raw_refresh)
    auth_session = AuthSession(
        id=uuid.uuid4(),
        user_id=user.id,
        device_id=clean_device_id,
        refresh_token_hash=refresh_hash,
        expires_at=now + timedelta(seconds=settings.refresh_token_ttl_seconds),
        created_at=now,
    )
    session.add(auth_session)
    await session.commit()

    access_token = create_access_token(user_id=user.id, session_id=auth_session.id)
    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        token_type="bearer",
        expires_in=settings.access_token_ttl_seconds,
    )
