import hashlib
import secrets
import uuid
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.session import get_session
from app.models.entities import Agent

AGENT_KEY_HEADER = "X-Agent-Key"


def generate_agent_api_key() -> str:
    """Generate a high-entropy cryptographically secure agent API key."""
    return f"agk_{secrets.token_urlsafe(32)}"


def hash_agent_key(raw_key: str) -> str:
    """Compute SHA-256 hash digest of the raw agent API key."""
    return hashlib.sha256(raw_key.strip().encode("utf-8")).hexdigest()


async def issue_agent_key(
    session: AsyncSession,
    business_id: uuid.UUID,
    version: str | None = None,
) -> tuple[Agent, str]:
    """Issue a new agent with a fresh API key.

    Returns the created Agent ORM object and the plaintext API key (shown only once).
    """
    raw_key = generate_agent_api_key()
    key_hash = hash_agent_key(raw_key)

    agent = Agent(
        business_id=business_id,
        key_hash=key_hash,
        version=version,
        status="active",
    )
    session.add(agent)
    await session.flush()
    return agent, raw_key


async def rotate_agent_key(
    session: AsyncSession,
    agent: Agent,
) -> str:
    """Rotate an existing agent's API key.

    Invalidates the old key hash and returns the new plaintext key (shown only once).
    """
    new_raw_key = generate_agent_api_key()
    agent.key_hash = hash_agent_key(new_raw_key)
    await session.flush()
    return new_raw_key


async def revoke_agent(
    session: AsyncSession,
    agent: Agent,
) -> None:
    """Revoke an agent, blocking all future sync and heartbeat requests."""
    agent.status = "revoked"
    await session.flush()


async def authenticate_agent(
    session: Annotated[AsyncSession, Depends(get_session)],
    x_agent_key: Annotated[str | None, Header(alias=AGENT_KEY_HEADER)] = None,
) -> Agent:
    """FastAPI dependency to authenticate requests from ONE Agent.

    Extracts API key strictly from X-Agent-Key header, hashes it,
    validates active status, and resolves the tenant context (agent.business_id).
    """
    if not x_agent_key or not x_agent_key.strip():
        raise AppError(
            code="AGENT_KEY_MISSING",
            message=f"{AGENT_KEY_HEADER} header is required",
            status_code=401,
        )

    raw_key = x_agent_key.strip()
    computed_hash = hash_agent_key(raw_key)
    result = await session.execute(
        select(Agent).where(Agent.key_hash == computed_hash)
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise AppError(
            code="AGENT_KEY_INVALID",
            message="Invalid agent API key",
            status_code=401,
        )

    if agent.status != "active":
        raise AppError(
            code="AGENT_REVOKED",
            message="Agent is revoked or disabled",
            status_code=403,
        )

    return agent

