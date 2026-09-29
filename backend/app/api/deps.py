"""Reusable FastAPI dependencies."""
import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import decode_access_token
from app.core.time import as_utc, utcnow
from app.db.session import get_session
from app.models.entities import AuthSession, User


@dataclass
class AuthenticatedCustomer:
    """Authenticated customer and session context."""

    user: User
    session: AuthSession


async def get_current_customer(
    session: Annotated[AsyncSession, Depends(get_session)],
    authorization: Annotated[str | None, Header()] = None,
) -> AuthenticatedCustomer:
    """FastAPI dependency to authenticate customer requests via Bearer JWT.

    Validates:
    - Authorization: Bearer <token>
    - Expiration & signature of JWT
    - AuthSession existence, not revoked, and not expired
    - User existence and not deleted
    """
    if not authorization:
        raise AppError(
            code="UNAUTHORIZED",
            message="Authorization header is required",
            status_code=401,
        )

    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise AppError(
            code="INVALID_AUTHORIZATION_HEADER",
            message="Authorization header must follow 'Bearer <token>' format",
            status_code=401,
        )

    token = parts[1].strip()
    payload = decode_access_token(token)

    try:
        user_id = uuid.UUID(payload["sub"])
        session_id = uuid.UUID(payload["sid"])
    except (KeyError, ValueError, TypeError) as err:
        raise AppError(
            code="INVALID_TOKEN",
            message="Invalid access token claims",
            status_code=401,
        ) from err

    # Check session status in database
    auth_session = (
        await session.execute(
            select(AuthSession).where(AuthSession.id == session_id)
        )
    ).scalar_one_or_none()

    if not auth_session:
        raise AppError(
            code="SESSION_NOT_FOUND",
            message="Session not found",
            status_code=401,
        )

    if auth_session.revoked_at is not None:
        raise AppError(
            code="SESSION_REVOKED",
            message="Session has been revoked",
            status_code=401,
        )

    if as_utc(auth_session.expires_at) <= utcnow():
        raise AppError(
            code="SESSION_EXPIRED",
            message="Session has expired",
            status_code=401,
        )

    if auth_session.user_id != user_id:
        raise AppError(
            code="INVALID_TOKEN",
            message="Session user mismatch",
            status_code=401,
        )

    # Check user existence and soft-deletion
    user = (
        await session.execute(
            select(User).where(User.id == user_id, User.deleted_at.is_(None))
        )
    ).scalar_one_or_none()

    if not user:
        raise AppError(
            code="USER_NOT_FOUND",
            message="Customer account not found or deactivated",
            status_code=401,
        )

    return AuthenticatedCustomer(user=user, session=auth_session)


async def get_current_user(
    auth_context: Annotated[AuthenticatedCustomer, Depends(get_current_customer)],
) -> User:
    """Dependency that returns the authenticated User entity directly."""
    return auth_context.user
