import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import (
    build_whatsapp_login_url,
    create_access_token,
    generate_challenge_code,
    generate_refresh_token,
    hash_challenge_code,
    hash_refresh_token,
)
from app.core.time import as_utc, utcnow
from app.db.session import get_session
from app.models.entities import AuthSession, LoginChallenge
from app.schemas.auth import (
    ChallengeStatusResponse,
    CreateChallengeRequest,
    CreateChallengeResponse,
    LogoutRequest,
    LogoutResponse,
    RefreshTokenRequest,
    TokenResponse,
)
from app.services.rate_limiter import RateLimiter, get_rate_limiter
from app.services.user_service import get_or_create_user_by_phone

router = APIRouter(prefix="/auth", tags=["Customer Auth"])


@router.post("/challenge", response_model=CreateChallengeResponse)
async def create_challenge(
    body: CreateChallengeRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> CreateChallengeResponse:
    """Create a new WhatsApp reverse login challenge for the customer app."""
    client_ip = request.client.host if request.client else "unknown"

    # Enforce rate limiting by device_id and IP
    if await limiter.is_rate_limited(
        f"dev:{body.device_id}",
        settings.auth_challenge_device_limit,
        settings.auth_challenge_rate_window_seconds,
    ):
        raise AppError(
            code="RATE_LIMIT_EXCEEDED",
            message="Too many challenge requests from this device. Please try again later.",
            status_code=429,
        )

    if await limiter.is_rate_limited(
        f"ip:{client_ip}",
        settings.auth_challenge_ip_limit,
        settings.auth_challenge_rate_window_seconds,
    ):
        raise AppError(
            code="RATE_LIMIT_EXCEEDED",
            message="Too many challenge requests from this IP. Please try again later.",
            status_code=429,
        )

    # Retry loop (up to 5 attempts) to guarantee uniqueness on collision
    max_retries = 5
    challenge: LoginChallenge | None = None
    code = ""
    expires_at = utcnow() + timedelta(seconds=settings.challenge_ttl_seconds)

    for attempt in range(max_retries):
        code = generate_challenge_code()
        code_digest = hash_challenge_code(code)
        expires_at = utcnow() + timedelta(seconds=settings.challenge_ttl_seconds)

        candidate = LoginChallenge(
            device_id=body.device_id,
            code_hash=code_digest,
            status="pending",
            expires_at=expires_at,
        )
        try:
            async with session.begin_nested():
                session.add(candidate)
                await session.flush()
            await session.commit()
            challenge = candidate
            break
        except IntegrityError:
            challenge = None
            if attempt == max_retries - 1:
                await session.rollback()
                raise AppError(
                    code="CHALLENGE_GENERATION_FAILED",
                    message="Failed to generate unique login challenge. Please try again later.",
                    status_code=500,
                )

    if challenge is None:
        raise AppError(
            code="CHALLENGE_GENERATION_FAILED",
            message="Failed to generate unique login challenge. Please try again later.",
            status_code=500,
        )

    login_url = build_whatsapp_login_url(code)

    return CreateChallengeResponse(
        challenge_id=challenge.id,
        code=code,
        login_url=login_url,
        expires_in=settings.challenge_ttl_seconds,
        expires_at=expires_at,
    )


@router.get(
    "/challenge/{challenge_id}",
    response_model=ChallengeStatusResponse,
    response_model_exclude_none=True,
)
async def get_challenge_status(
    challenge_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    x_device_id: Annotated[str | None, Header(alias="X-Device-Id")] = None,
) -> ChallengeStatusResponse:
    """Check challenge status and exchange confirmed challenge for access & refresh tokens."""
    normalized_device_id = x_device_id.strip() if x_device_id else ""
    if not normalized_device_id:
        raise AppError(
            code="DEVICE_HEADER_MISSING",
            message="X-Device-Id header is required to verify challenge ownership",
            status_code=400,
        )

    # Acquire row lock to ensure single-use token issuance under concurrent polling
    stmt = (
        select(LoginChallenge)
        .where(LoginChallenge.id == challenge_id)
        .with_for_update()
    )
    challenge = (await session.execute(stmt)).scalar_one_or_none()

    if not challenge:
        raise AppError(
            code="CHALLENGE_NOT_FOUND",
            message="Login challenge not found",
            status_code=404,
        )

    # Validate device binding
    if challenge.device_id != normalized_device_id:
        raise AppError(
            code="DEVICE_MISMATCH",
            message="Device identifier does not match challenge owner",
            status_code=403,
        )

    # Handle already consumed challenge
    if challenge.status == "consumed":
        raise AppError(
            code="CHALLENGE_ALREADY_CONSUMED",
            message="Challenge has already been exchanged for tokens",
            status_code=409,
        )

    # Handle expiration
    if challenge.status == "expired" or as_utc(challenge.expires_at) <= utcnow():
        if challenge.status == "pending":
            challenge.status = "expired"
            await session.commit()
        return ChallengeStatusResponse(status="expired")

    # If pending, return pending status
    if challenge.status == "pending":
        return ChallengeStatusResponse(status="pending")

    # If confirmed, atomically issue tokens and transition to consumed
    if challenge.status == "confirmed":
        if not challenge.phone:
            raise AppError(
                code="CHALLENGE_PHONE_MISSING",
                message="Confirmed challenge is missing associated customer phone",
                status_code=500,
            )

        # Resolve or create customer User atomically
        user = await get_or_create_user_by_phone(session, challenge.phone)

        # Create new customer auth session
        raw_refresh = generate_refresh_token()
        refresh_hash = hash_refresh_token(raw_refresh)
        session_expires_at = utcnow() + timedelta(
            seconds=settings.refresh_token_ttl_seconds
        )

        auth_session = AuthSession(
            user_id=user.id,
            device_id=challenge.device_id,
            refresh_token_hash=refresh_hash,
            expires_at=session_expires_at,
        )
        session.add(auth_session)
        challenge.status = "consumed"
        await session.flush()

        access_jwt = create_access_token(
            user_id=user.id,
            session_id=auth_session.id,
        )
        await session.commit()

        return ChallengeStatusResponse(
            status="confirmed",
            access_token=access_jwt,
            refresh_token=raw_refresh,
            token_type="bearer",
            expires_in=settings.access_token_ttl_seconds,
        )

    return ChallengeStatusResponse(status=challenge.status)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    body: RefreshTokenRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TokenResponse:
    """Rotate refresh token and issue a fresh access JWT."""
    req_hash = hash_refresh_token(body.refresh_token)

    # Acquire row lock to prevent race condition / multiple rotation winners
    stmt = (
        select(AuthSession)
        .where(AuthSession.refresh_token_hash == req_hash)
        .with_for_update()
    )
    auth_session = (await session.execute(stmt)).scalar_one_or_none()

    if not auth_session or auth_session.revoked_at is not None:
        raise AppError(
            code="INVALID_REFRESH_TOKEN",
            message="Invalid, reused, or revoked refresh token",
            status_code=401,
        )

    if as_utc(auth_session.expires_at) <= utcnow():
        raise AppError(
            code="REFRESH_TOKEN_EXPIRED",
            message="Refresh token has expired",
            status_code=401,
        )

    # Rotate refresh token
    new_raw_refresh = generate_refresh_token()
    auth_session.refresh_token_hash = hash_refresh_token(new_raw_refresh)
    auth_session.last_rotated_at = utcnow()

    new_access_jwt = create_access_token(
        user_id=auth_session.user_id,
        session_id=auth_session.id,
    )
    await session.commit()

    return TokenResponse(
        access_token=new_access_jwt,
        refresh_token=new_raw_refresh,
        token_type="bearer",
        expires_in=settings.access_token_ttl_seconds,
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    body: LogoutRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LogoutResponse:
    """Revoke auth session by refresh token."""
    req_hash = hash_refresh_token(body.refresh_token)

    stmt = (
        select(AuthSession)
        .where(AuthSession.refresh_token_hash == req_hash)
        .with_for_update()
    )
    auth_session = (await session.execute(stmt)).scalar_one_or_none()

    if auth_session and auth_session.revoked_at is None:
        auth_session.revoked_at = utcnow()
        await session.commit()

    return LogoutResponse(status="ok")
