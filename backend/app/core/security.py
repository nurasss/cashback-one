import hashlib
import hmac
import secrets
import urllib.parse
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.core.config import settings
from app.core.errors import AppError

# Safe alphanumeric alphabet without ambiguous characters (no 0/O, 1/I/L)
CHALLENGE_CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
CHALLENGE_CODE_LENGTH = 8


def generate_challenge_code() -> str:
    """Generate cryptographically secure 8-character challenge code."""
    return "".join(
        secrets.choice(CHALLENGE_CODE_ALPHABET)
        for _ in range(CHALLENGE_CODE_LENGTH)
    )


def hash_challenge_code(code: str, secret_key: str | None = None) -> str:
    """Compute HMAC-SHA256 digest of normalized challenge code."""
    key = (secret_key or settings.auth_challenge_hash_key).encode("utf-8")
    normalized = code.strip().upper().encode("utf-8")
    return hmac.new(key, normalized, hashlib.sha256).hexdigest()


def build_whatsapp_login_url(code: str, login_number: str | None = None) -> str:
    """Build wa.me URL with phone without '+' and URL-encoded code."""
    raw_num = login_number or settings.whatsapp_login_number
    digits_phone = "".join(c for c in raw_num if c.isdigit())
    encoded_text = urllib.parse.quote(code.strip())
    return f"https://wa.me/{digits_phone}?text={encoded_text}"


def generate_refresh_token() -> str:
    """Generate high-entropy random opaque refresh token."""
    return f"rfr_{secrets.token_urlsafe(48)}"


def hash_refresh_token(raw_token: str) -> str:
    """Compute SHA-256 digest of raw refresh token for safe DB storage."""
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


def create_access_token(
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    expires_delta_seconds: int | None = None,
) -> str:
    """Issue customer access JWT with standard claims."""
    now = datetime.now(UTC)
    ttl = expires_delta_seconds or settings.access_token_ttl_seconds
    expire_dt = now + timedelta(seconds=ttl)

    payload = {
        "sub": str(user_id),
        "sid": str(session_id),
        "typ": "access",
        "iat": int(now.timestamp()),
        "exp": int(expire_dt.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_signing_key, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    """Verify and decode customer access JWT."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_signing_key,
            algorithms=["HS256"],
            options={"require": ["sub", "sid", "typ", "iat", "exp"]},
        )
        if payload.get("typ") != "access":
            raise AppError(
                code="INVALID_TOKEN_TYPE",
                message="Token is not an access token",
                status_code=401,
            )
        return payload
    except jwt.ExpiredSignatureError as err:
        raise AppError(
            code="TOKEN_EXPIRED",
            message="Access token has expired",
            status_code=401,
        ) from err
    except jwt.PyJWTError as err:
        raise AppError(
            code="INVALID_TOKEN",
            message="Invalid or tampered access token",
            status_code=401,
        ) from err


def generate_sms_otp() -> str:
    """Generate cryptographically secure 6-digit numeric OTP."""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_sms_otp(phone: str, otp: str, secret_key: str | None = None) -> str:
    """Compute HMAC-SHA256 digest of normalized phone and OTP.

    Domain-separated format: '{normalized_phone}:{otp}'.
    """
    key = (secret_key or settings.sms_otp_hash_key).encode()
    payload = f"{phone.strip()}:{otp.strip()}".encode()
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def verify_sms_otp_hash(
    phone: str,
    otp: str,
    expected_hash: str,
    secret_key: str | None = None,
) -> bool:
    """Constant-time verification of SMS OTP HMAC-SHA256 digest."""
    computed_hash = hash_sms_otp(phone, otp, secret_key)
    return hmac.compare_digest(computed_hash, expected_hash)

