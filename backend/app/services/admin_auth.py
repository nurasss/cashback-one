import asyncio
import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.core.time import utcnow
from app.db.session import get_session
from app.models.admin import AdminSession, AdminUser
from app.services.admin_security import (
    ADMIN_REFRESH_PREFIX,
    admin_refresh_token_hash,
    create_admin_access_token,
    decode_admin_access_token,
    dummy_password_hash,
    generate_admin_refresh_token,
    login_rate_key,
    verify_admin_password,
)
from app.services.rate_limiter import RateLimiter


async def check_admin_rate_limit(
    limiter: RateLimiter, login: str, request: Request
) -> None:
    source_ip = request.client.host if request.client else "unknown"
    if await limiter.is_rate_limited(
        login_rate_key("login", login),
        settings.admin_login_limit,
        settings.admin_login_rate_window_seconds,
    ):
        raise AppError("ADMIN_RATE_LIMITED", "Слишком много попыток входа. Попробуйте позже.", 429)
    if await limiter.is_rate_limited(
        login_rate_key("ip", source_ip),
        settings.admin_login_ip_limit,
        settings.admin_login_rate_window_seconds,
    ):
        raise AppError("ADMIN_RATE_LIMITED", "Слишком много попыток входа. Попробуйте позже.", 429)


def _fresh_session(admin_id: uuid.UUID, raw_refresh: str) -> AdminSession:
    now = utcnow()
    return AdminSession(
        id=uuid.uuid4(),
        admin_user_id=admin_id,
        refresh_token_hash=admin_refresh_token_hash(raw_refresh),
        created_at=now,
        expires_at=now + timedelta(seconds=settings.admin_refresh_token_ttl_seconds),
    )


def _token_pair(admin_id: uuid.UUID, session_id: uuid.UUID) -> dict[str, object]:
    return {
        "access_token": create_admin_access_token(admin_id, session_id),
        "token_type": "bearer",
        "expires_in": settings.admin_access_token_ttl_seconds,
    }


async def login_admin(
    db: AsyncSession,
    login: str,
    password: str,
    request: Request,
    limiter: RateLimiter,
) -> tuple[AdminUser, AdminSession, str]:
    normalized = login.strip().lower()
    await check_admin_rate_limit(limiter, normalized, request)
    admin = await db.scalar(select(AdminUser).where(AdminUser.login == normalized))
    stored_hash = admin.password_hash if admin is not None else dummy_password_hash()
    password_matches = await asyncio.to_thread(verify_admin_password, stored_hash, password)
    if admin is None or not password_matches or not admin.is_active:
        raise AppError("INVALID_CREDENTIALS", "Неверный логин или пароль", 401)

    raw_refresh = generate_admin_refresh_token()
    session = _fresh_session(admin.id, raw_refresh)
    db.add(session)
    await db.commit()
    await db.refresh(admin)
    return admin, session, raw_refresh


async def rotate_admin_session(db: AsyncSession, raw_refresh: str) -> tuple[AdminUser, AdminSession, str]:
    now = utcnow()
    old_hash = admin_refresh_token_hash(raw_refresh)
    next_raw_refresh = generate_admin_refresh_token()
    result = await db.execute(
        update(AdminSession)
        .where(
            AdminSession.refresh_token_hash == old_hash,
            AdminSession.revoked_at.is_(None),
            AdminSession.expires_at > now,
        )
        .values(
            refresh_token_hash=admin_refresh_token_hash(next_raw_refresh),
            last_rotated_at=now,
        )
        .returning(AdminSession.id, AdminSession.admin_user_id, AdminSession.expires_at)
    )
    row = result.one_or_none()
    if row is None:
        raise AppError("ADMIN_UNAUTHENTICATED", "Admin session expired. Sign in again.", 401)
    admin = await db.scalar(
        select(AdminUser).where(AdminUser.id == row.admin_user_id, AdminUser.is_active.is_(True))
    )
    if admin is None:
        await db.execute(
            update(AdminSession).where(AdminSession.id == row.id).values(revoked_at=now)
        )
        await db.commit()
        raise AppError("ADMIN_UNAUTHENTICATED", "Admin session expired. Sign in again.", 401)
    session = await db.get(AdminSession, row.id)
    if session is None:
        raise AppError("ADMIN_UNAUTHENTICATED", "Admin session expired. Sign in again.", 401)
    await db.commit()
    return admin, session, next_raw_refresh


async def authenticate_admin(
    db: Annotated[AsyncSession, Depends(get_session)],
    authorization: Annotated[str | None, Header()] = None,
) -> AdminUser:
    if not authorization:
        raise AppError("ADMIN_UNAUTHENTICATED", "Admin authentication required", 401)
    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise AppError("ADMIN_UNAUTHENTICATED", "Admin authentication required", 401)
    admin_id, session_id = decode_admin_access_token(parts[1].strip())
    row = (
        await db.execute(
            select(AdminUser, AdminSession)
            .join(AdminSession, AdminSession.admin_user_id == AdminUser.id)
            .where(
                AdminUser.id == admin_id,
                AdminUser.is_active.is_(True),
                AdminSession.id == session_id,
                AdminSession.revoked_at.is_(None),
                AdminSession.expires_at > utcnow(),
            )
        )
    ).one_or_none()
    if row is None:
        raise AppError("ADMIN_UNAUTHENTICATED", "Admin authentication required", 401)
    admin: AdminUser = row[0]
    if not ((admin.role == "superadmin" and admin.business_id is None) or (
        admin.role == "business_manager" and admin.business_id is not None
    )):
        raise AppError("ADMIN_UNAUTHENTICATED", "Admin authentication required", 401)
    return admin


async def revoke_admin_session(db: AsyncSession, raw_refresh: str | None) -> None:
    if not raw_refresh or not raw_refresh.startswith(ADMIN_REFRESH_PREFIX):
        return
    await db.execute(
        update(AdminSession)
        .where(
            AdminSession.refresh_token_hash == admin_refresh_token_hash(raw_refresh),
            AdminSession.revoked_at.is_(None),
        )
        .values(revoked_at=utcnow())
    )
    await db.commit()
