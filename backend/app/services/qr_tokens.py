"""Dynamic card QR tokens.

Token = "C1" + base32(card_id[16] | expires_unix[4] | HMAC-SHA256(key, prefix|payload)[:10]).
It is stateless, expires after QR_TOKEN_TTL_SECONDS and uses only QR alphanumeric characters
(digits and upper-case letters) so the code stays compact. The signing key is derived from
JWT_SIGNING_KEY with a fixed domain label, so no extra secret has to be deployed.
"""
import base64
import hashlib
import hmac
import struct
import uuid
from datetime import UTC, datetime, timedelta

from app.core.config import settings
from app.core.time import utcnow

TOKEN_PREFIX = "C1"
_MAC_BYTES = 10
_PAYLOAD_BYTES = 20


def _signing_key() -> bytes:
    return hmac.new(
        settings.jwt_signing_key.encode("utf-8"), b"cashback-one/card-qr/v1", hashlib.sha256
    ).digest()


def _mac(payload: bytes) -> bytes:
    return hmac.new(_signing_key(), TOKEN_PREFIX.encode() + payload, hashlib.sha256).digest()[:_MAC_BYTES]


def issue_card_token(card_id: uuid.UUID, now: datetime | None = None) -> tuple[str, datetime]:
    issued = now or utcnow()
    expires_at = (issued + timedelta(seconds=settings.qr_token_ttl_seconds)).replace(microsecond=0)
    payload = card_id.bytes + struct.pack(">I", int(expires_at.timestamp()))
    raw = payload + _mac(payload)
    token = TOKEN_PREFIX + base64.b32encode(raw).decode("ascii").rstrip("=")
    return token, expires_at


def verify_card_token(token: str, now: datetime | None = None) -> uuid.UUID | None:
    """Return the card id for a valid, unexpired token, otherwise None."""
    value = token.strip().upper()
    if not value.startswith(TOKEN_PREFIX) or len(value) > 64:
        return None
    body = value[len(TOKEN_PREFIX):]
    try:
        raw = base64.b32decode(body + "=" * (-len(body) % 8))
    except ValueError:
        return None
    if len(raw) != _PAYLOAD_BYTES + _MAC_BYTES:
        return None
    payload, mac = raw[:_PAYLOAD_BYTES], raw[_PAYLOAD_BYTES:]
    if not hmac.compare_digest(mac, _mac(payload)):
        return None
    (expires_unix,) = struct.unpack(">I", payload[16:])
    if datetime.fromtimestamp(expires_unix, tz=UTC) <= (now or utcnow()):
        return None
    return uuid.UUID(bytes=payload[:16])
