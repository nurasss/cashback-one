"""Public unauthenticated endpoints for customer mobile applications."""
from __future__ import annotations

import hashlib
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.entities import Business
from app.schemas.admin_content import PublicSplashResponse

router = APIRouter(prefix="/public", tags=["Public App"])


@router.get("/app-splash", response_model=PublicSplashResponse)
async def get_public_app_splash(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    app_id: Annotated[str | None, Query(description="Client Android app package id, e.g. kz.cashbackone.keremet")] = None,
    business_id: Annotated[uuid.UUID | None, Query(description="Business UUID")] = None,
) -> Response:
    """Public minimal splash screen configuration for pre-auth mobile app launch.

    Does not require customer authentication, card bindings, or personal tokens.
    Resolves business by client android_app_id or business_id.
    Returns 200 with enabled=false if no splash configured or business inactive.
    Supports ETag / 304 Not Modified caching.
    """
    business: Business | None = None

    if app_id:
        clean_app_id = app_id.strip()
        if clean_app_id:
            business = await session.scalar(
                select(Business).where(
                    Business.android_app_id == clean_app_id,
                    Business.status == "active",
                )
            )

    if business is None and business_id:
        business = await session.scalar(
            select(Business).where(
                Business.id == business_id,
                Business.status == "active",
            )
        )

    if business is None:
        splash_obj = PublicSplashResponse(enabled=False)
    else:
        raw = business.splash_config or {}
        enabled = bool(raw.get("enabled", False))
        if not enabled:
            splash_obj = PublicSplashResponse(business_id=business.id, enabled=False)
        else:
            splash_obj = PublicSplashResponse(
                business_id=business.id,
                enabled=True,
                media_type=raw.get("media_type"),
                media_url=raw.get("media_url"),
                width=raw.get("width"),
                height=raw.get("height"),
                duration_seconds=raw.get("duration_seconds"),
                file_size=raw.get("file_size"),
                version=raw.get("version"),
            )

    json_str = splash_obj.model_dump_json()
    etag = f'"{hashlib.sha256(json_str.encode("utf-8")).hexdigest()[:32]}"'
    cache_control = "public, max-age=60"

    if_none_match = request.headers.get("if-none-match")
    if if_none_match:
        client_tags = [t.strip() for t in if_none_match.split(",")]
        if etag in client_tags or etag.strip('"') in client_tags or "*" in client_tags:
            return Response(
                status_code=304,
                headers={"ETag": etag, "Cache-Control": cache_control},
            )

    return Response(
        content=json_str,
        media_type="application/json",
        headers={"ETag": etag, "Cache-Control": cache_control},
    )
