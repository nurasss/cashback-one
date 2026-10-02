from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin_deps import require_admin_origin
from app.core.config import settings
from app.core.errors import AppError
from app.core.time import as_utc, utcnow
from app.db.session import get_session
from app.schemas.admin import AdminLoginRequest, AdminTokenResponse, LogoutResponse
from app.services.admin_auth import (
    _token_pair,
    login_admin,
    revoke_admin_session,
    rotate_admin_session,
)
from app.services.admin_security import COOKIE_NAME, COOKIE_PATH, secure_admin_cookie
from app.services.rate_limiter import RateLimiter, get_rate_limiter

router = APIRouter(dependencies=[Depends(require_admin_origin)])


def _set_refresh_cookie(response: Response, request: Request, refresh_token: str, max_age: int) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=refresh_token,
        max_age=max(0, max_age),
        path=COOKIE_PATH,
        secure=secure_admin_cookie(request),
        httponly=True,
        samesite="lax",
    )


def _delete_refresh_cookie(response: Response, request: Request) -> None:
    response.delete_cookie(
        key=COOKIE_NAME,
        path=COOKIE_PATH,
        secure=secure_admin_cookie(request),
        httponly=True,
        samesite="lax",
    )


@router.post("/auth/login", response_model=AdminTokenResponse)
async def admin_login(
    body: AdminLoginRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_session)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> dict[str, object]:
    admin, session, raw_refresh = await login_admin(
        db, body.login, body.password, request, limiter
    )
    _set_refresh_cookie(response, request, raw_refresh, settings.admin_refresh_token_ttl_seconds)
    response.headers["Cache-Control"] = "no-store, private"
    return _token_pair(admin.id, session.id)


@router.post("/auth/refresh", response_model=AdminTokenResponse)
async def admin_refresh(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_session)],
    refresh_token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> dict[str, object]:
    if not refresh_token:
        raise AppError("ADMIN_UNAUTHENTICATED", "Admin session expired. Sign in again.", 401)
    if not refresh_token.startswith("adm_rfr_"):
        raise AppError("ADMIN_UNAUTHENTICATED", "Admin session expired. Sign in again.", 401)
    admin, session, raw_refresh = await rotate_admin_session(db, refresh_token)
    remaining = int((as_utc(session.expires_at) - utcnow()).total_seconds())
    _set_refresh_cookie(response, request, raw_refresh, remaining)
    response.headers["Cache-Control"] = "no-store, private"
    return _token_pair(admin.id, session.id)


@router.post("/auth/logout", response_model=LogoutResponse)
async def admin_logout(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_session)],
    refresh_token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> LogoutResponse:
    await revoke_admin_session(db, refresh_token)
    _delete_refresh_cookie(response, request)
    response.headers["Cache-Control"] = "no-store, private"
    return LogoutResponse()
