"""Authentication and lifecycle of POS cash register access keys."""
import hashlib
import secrets
import uuid
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.time import as_utc, utcnow
from app.db.session import get_session
from app.models.entities import PosKey

POS_KEY_HEADER = "X-Pos-Key"


def generate_pos_api_key() -> str:
    """Generate a high-entropy cryptographically secure POS API key (prefix pos_)."""
    return f"pos_{secrets.token_urlsafe(32)}"


def hash_pos_key(raw_key: str) -> str:
    """Compute SHA-256 hash digest of the raw POS API key."""
    return hashlib.sha256(raw_key.strip().encode("utf-8")).hexdigest()


async def issue_pos_key(
    session: AsyncSession,
    business_id: uuid.UUID,
    name: str,
) -> tuple[PosKey, str]:
    """Issue a new POS key for a cash register.

    Returns the created PosKey ORM instance and the plaintext API key (shown only once).
    """
    raw_key = generate_pos_api_key()
    key_hash = hash_pos_key(raw_key)

    pos_key = PosKey(
        business_id=business_id,
        name=name.strip(),
        key_hash=key_hash,
        created_at=utcnow(),
    )
    session.add(pos_key)
    await session.flush()
    return pos_key, raw_key


async def revoke_pos_key(
    session: AsyncSession,
    pos_key: PosKey,
) -> PosKey:
    """Revoke a POS key, blocking all future redemption requests."""
    if pos_key.revoked_at is None:
        pos_key.revoked_at = utcnow()
        await session.flush()
    return pos_key


async def authenticate_pos_key(
    session: Annotated[AsyncSession, Depends(get_session)],
    x_pos_key: Annotated[str | None, Header(alias=POS_KEY_HEADER)] = None,
) -> PosKey:
    """FastAPI dependency to authenticate requests from POS cash registers.

    Extracts API key strictly from X-Pos-Key header, hashes it,
    validates active status, updates last_used_at at most once per minute,
    and returns the authenticated PosKey context.
    """
    if not x_pos_key or not x_pos_key.strip():
        raise AppError(
            code="POS_KEY_MISSING",
            message=f"{POS_KEY_HEADER} header is required",
            status_code=401,
        )

    raw_key = x_pos_key.strip()
    computed_hash = hash_pos_key(raw_key)
    result = await session.execute(
        select(PosKey).where(PosKey.key_hash == computed_hash)
    )
    pos_key = result.scalar_one_or_none()

    if not pos_key:
        raise AppError(
            code="POS_KEY_INVALID",
            message="Invalid POS API key",
            status_code=401,
        )

    if pos_key.revoked_at is not None:
        raise AppError(
            code="POS_KEY_REVOKED",
            message="POS key has been revoked",
            status_code=401,
        )

    now = utcnow()
    if pos_key.last_used_at is None or (now - as_utc(pos_key.last_used_at)).total_seconds() >= 60:
        pos_key.last_used_at = now
        await session.flush()

    return pos_key
