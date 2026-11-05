"""Customer app endpoints: profile, promotions, notifications, badges, dynamic card QR and wallet passes."""
import hashlib
import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings, settings
from app.core.errors import AppError
from app.core.time import as_utc, utcnow
from app.db.session import get_session
from app.models.entities import Business, BusinessStore, Card, Device, User, UserCard
from app.schemas.customer_app import (
    AppStoreItem,
    BadgesResponse,
    CardQrResponse,
    CustomerAppContentResponse,
    CustomerAppTexts,
    CustomerLocalizedText,
    NotificationsResponse,
    ProfileResponse,
    ProfileUpdateRequest,
    PromotionItem,
    PromotionsResponse,
    PushTokenDeleteRequest,
    PushTokenRegisterRequest,
    WalletAvailability,
    WalletLinkRequest,
    WalletLinkResponse,
)
from app.services import content_service, wallet_passes
from app.services.image_service import process_and_store_image
from app.services.media_storage import (
    MediaStorage,
    get_media_storage,
    maybe_cleanup_old_media_file,
)
from app.services.qr_tokens import issue_card_token
from app.services.rate_limiter import RateLimiter, get_rate_limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/me", tags=["Customer App"])


@router.get("/profile", response_model=ProfileResponse)
async def get_profile(
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProfileResponse:
    return ProfileResponse.model_validate(current_user)


@router.patch("/profile", response_model=ProfileResponse)
async def update_profile(
    body: ProfileUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProfileResponse:
    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "language" and value is None:
            continue
        setattr(current_user, field, value)
    await session.commit()
    return ProfileResponse.model_validate(current_user)


@router.post("/avatar", response_model=ProfileResponse)
async def upload_avatar(
    file: Annotated[UploadFile, File(...)],
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[MediaStorage, Depends(get_media_storage)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    settings_obj: Annotated[Settings, Depends(get_settings)],
) -> ProfileResponse:
    rate_key = f"avatar_upload:user:{current_user.id}"
    if await limiter.is_rate_limited(
        rate_key,
        settings_obj.avatar_upload_user_limit,
        settings_obj.avatar_upload_window_seconds,
    ):
        raise AppError(
            "RATE_LIMIT_EXCEEDED",
            "Too many avatar upload attempts. Please try again later.",
            status_code=429,
        )

    max_bytes = settings_obj.avatar_max_upload_bytes
    total_bytes = 0
    chunks: list[bytes] = []
    chunk_size = 65536
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total_bytes += len(chunk)
        if total_bytes > max_bytes:
            raise AppError(
                "FILE_TOO_LARGE",
                f"File size exceeds maximum limit of {max_bytes} bytes.",
                status_code=413,
            )
        chunks.append(chunk)

    raw_bytes = b"".join(chunks)
    if not raw_bytes:
        raise AppError("VALIDATION_ERROR", "Uploaded file is empty.", status_code=422)

    img_res = await process_and_store_image(
        raw_bytes=raw_bytes,
        purpose="avatar",
        settings=settings_obj,
        storage=storage,
    )
    new_url = img_res.url
    old_url = current_user.avatar_url
    current_user.avatar_url = new_url

    try:
        await session.commit()
    except Exception:
        base = settings_obj.media_public_base_url.rstrip("/") + "/"
        if new_url.startswith(base):
            rel_path = new_url[len(base):]
            try:
                await storage.delete(rel_path)
            except (AppError, OSError, ValueError):
                logger.warning("Failed to cleanup new avatar file after DB error")
        raise

    if old_url:
        try:
            await maybe_cleanup_old_media_file(
                db=session,
                storage=storage,
                old_url=old_url,
                settings=settings_obj,
            )
        except (AppError, OSError, ValueError) as exc:
            logger.warning("Failed to cleanup old avatar: %s", exc)

    return ProfileResponse.model_validate(current_user)


@router.delete("/avatar", response_model=ProfileResponse)
async def delete_avatar(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[MediaStorage, Depends(get_media_storage)],
    settings_obj: Annotated[Settings, Depends(get_settings)],
) -> ProfileResponse:
    old_url = current_user.avatar_url
    if old_url is not None:
        current_user.avatar_url = None
        await session.commit()
        try:
            await maybe_cleanup_old_media_file(
                db=session,
                storage=storage,
                old_url=old_url,
                settings=settings_obj,
            )
        except (AppError, OSError, ValueError) as exc:
            logger.warning("Failed to cleanup old avatar on delete: %s", exc)

    return ProfileResponse.model_validate(current_user)


@router.get("/promotions", response_model=PromotionsResponse)
async def promotions(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    business_id: Annotated[uuid.UUID | None, Query()] = None,
) -> PromotionsResponse:
    return await content_service.list_promotions(
        session, current_user, business_id=business_id
    )


@router.post("/promotions/seen", status_code=status.HTTP_204_NO_CONTENT)
async def promotions_seen(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    business_id: Annotated[uuid.UUID | None, Query()] = None,
) -> Response:
    await content_service.mark_promotions_seen(
        session, current_user, business_id=business_id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/promotions/{promotion_id}", response_model=PromotionItem)
async def promotion_detail(
    promotion_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    business_id: Annotated[uuid.UUID | None, Query()] = None,
) -> PromotionItem:
    return await content_service.get_promotion(
        session, current_user, promotion_id, business_id=business_id
    )


@router.get("/notifications", response_model=NotificationsResponse)
async def notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    business_id: Annotated[uuid.UUID | None, Query()] = None,
) -> NotificationsResponse:
    return await content_service.list_notifications(
        session, current_user, business_id=business_id
    )


@router.post("/notifications/read", status_code=status.HTTP_204_NO_CONTENT)
async def notifications_read(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    business_id: Annotated[uuid.UUID | None, Query()] = None,
) -> Response:
    await content_service.mark_notifications_read(
        session, current_user, business_id=business_id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/badges", response_model=BadgesResponse)
async def badges(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    business_id: Annotated[uuid.UUID | None, Query()] = None,
) -> BadgesResponse:
    return await content_service.badges(
        session, current_user, business_id=business_id
    )


async def _visible_card(session: AsyncSession, user: User, card_id: uuid.UUID) -> tuple[Card, Business]:
    row = (await session.execute(
        select(Card, Business)
        .join(UserCard, UserCard.card_id == Card.id)
        .join(Business, Business.id == Card.business_id)
        .where(
            Card.id == card_id,
            UserCard.user_id == user.id,
            UserCard.hidden_at.is_(None),
            Business.status == "active",
        )
    )).first()
    if row is None:
        raise AppError("CARD_NOT_FOUND", "Card not found in your wallet", 404)
    return row[0], row[1]


@router.get("/cards/{card_id}/qr", response_model=CardQrResponse)
async def card_qr(
    card_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CardQrResponse:
    """Short-lived signed QR token for a visible card of the customer (dynamic QR)."""
    await _visible_card(session, current_user, card_id)
    token, expires_at = issue_card_token(card_id)
    return CardQrResponse(
        token=token, expires_at=expires_at, ttl_seconds=settings.qr_token_ttl_seconds
    )


@router.get("/wallet", response_model=WalletAvailability)
async def wallet_availability(
    current_user: Annotated[User, Depends(get_current_user)],
) -> WalletAvailability:
    """Which phone wallets can receive a card pass on this server."""
    return WalletAvailability(apple=wallet_passes.apple_enabled(), google=wallet_passes.google_enabled())


@router.post("/cards/{card_id}/wallet", response_model=WalletLinkResponse)
async def card_wallet_link(
    card_id: uuid.UUID,
    body: WalletLinkRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WalletLinkResponse:
    """Link that adds the card (static barcode as QR) to Apple Wallet or Google Wallet."""
    card, business = await _visible_card(session, current_user, card_id)
    if card.is_blocked:
        raise AppError("CARD_BLOCKED", "Card is blocked", 409)
    if body.platform == "apple":
        if not wallet_passes.apple_enabled():
            raise AppError("WALLET_UNAVAILABLE", "Apple Wallet is not configured", 503)
        url, expires_at = wallet_passes.apple_link(card.id)
        return WalletLinkResponse(url=url, expires_at=expires_at)
    if not wallet_passes.google_enabled():
        raise AppError("WALLET_UNAVAILABLE", "Google Wallet is not configured", 503)
    return WalletLinkResponse(url=wallet_passes.google_save_url(card, business), expires_at=None)


@router.put("/push-token", status_code=status.HTTP_204_NO_CONTENT)
async def register_push_token(
    body: PushTokenRegisterRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    settings_obj: Annotated[Settings, Depends(get_settings)],
) -> Response:
    user_id = current_user.id
    rate_key = f"push_token:user:{user_id}"
    if await limiter.is_rate_limited(
        rate_key,
        settings_obj.push_token_user_limit,
        settings_obj.push_token_rate_window_seconds,
    ):
        raise AppError(
            "RATE_LIMIT_EXCEEDED",
            "Too many push token registration attempts. Please try again later.",
            status_code=429,
        )

    stmt = select(Device).where(Device.push_token == body.token)
    device = await session.scalar(stmt)
    now = utcnow()
    if device is not None:
        device.user_id = user_id
        device.platform = body.platform
        device.app_id = body.app_id
        device.disabled_at = None
        device.last_seen_at = now
        await session.commit()
    else:
        device = Device(
            user_id=user_id,
            push_token=body.token,
            platform=body.platform,
            app_id=body.app_id,
            created_at=now,
            last_seen_at=now,
            disabled_at=None,
        )
        session.add(device)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            # Concurrent registration race: another request inserted this token, update it
            stmt = select(Device).where(Device.push_token == body.token)
            device = await session.scalar(stmt)
            if device is not None:
                device.user_id = user_id
                device.platform = body.platform
                device.app_id = body.app_id
                device.disabled_at = None
                device.last_seen_at = now
                await session.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/push-token", status_code=status.HTTP_204_NO_CONTENT)
async def delete_push_token(
    body: PushTokenDeleteRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    stmt = select(Device).where(
        Device.push_token == body.token,
        Device.user_id == current_user.id,
    )
    device = await session.scalar(stmt)
    if device is not None and device.disabled_at is None:
        device.disabled_at = utcnow()
        await session.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/app-content", response_model=CustomerAppContentResponse)
async def get_app_content(
    business_id: uuid.UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    # 1. Customer must have an active visible card of this business
    card_exists = await session.scalar(
        select(Card.id)
        .join(UserCard, UserCard.card_id == Card.id)
        .where(
            UserCard.user_id == current_user.id,
            UserCard.hidden_at.is_(None),
            Card.business_id == business_id,
        )
        .limit(1)
    )
    if not card_exists:
        raise AppError("CUSTOMER_RESOURCE_NOT_FOUND", "Business content not found", 404)

    # 2. Business must exist and be active
    business = await session.get(Business, business_id)
    if not business or business.status != "active":
        raise AppError("CUSTOMER_RESOURCE_NOT_FOUND", "Business content not found", 404)

    # 3. Active stores ordered by sort_order ASC, created_at ASC, id ASC
    stores_stmt = (
        select(BusinessStore)
        .where(
            BusinessStore.business_id == business_id,
            BusinessStore.is_active.is_(True),
        )
        .order_by(
            BusinessStore.sort_order.asc(),
            BusinessStore.created_at.asc(),
            BusinessStore.id.asc(),
        )
    )
    stores = list((await session.scalars(stores_stmt)).all())

    # 4. updated_at is the latest modification timestamp among business and active stores
    all_timestamps = [as_utc(business.updated_at)] + [as_utc(s.updated_at) for s in stores]
    latest_updated_at = max(all_timestamps)

    raw_texts = business.app_texts or {}
    app_texts = CustomerAppTexts(
        home_store_note_lead=CustomerLocalizedText.model_validate(
            raw_texts.get("home_store_note_lead") or {}
        ),
        balance_delay_note=CustomerLocalizedText.model_validate(
            raw_texts.get("balance_delay_note") or {}
        ),
    )
    stores_payload = [AppStoreItem.model_validate(s) for s in stores]
    content_obj = CustomerAppContentResponse(
        business_id=business_id,
        stores=stores_payload,
        app_texts=app_texts,
        updated_at=latest_updated_at,
    )

    json_str = content_obj.model_dump_json()
    etag = f'"{hashlib.sha256(json_str.encode("utf-8")).hexdigest()[:32]}"'
    cache_control = "private, max-age=300"

    if_none_match = request.headers.get("if-none-match")
    if if_none_match:
        client_tags = [t.strip() for t in if_none_match.split(",")]
        if etag in client_tags or etag.strip('"') in client_tags or "*" in client_tags:
            return Response(
                status_code=304,
                headers={
                    "ETag": etag,
                    "Cache-Control": cache_control,
                },
            )

    return Response(
        content=json_str,
        media_type="application/json",
        headers={
            "ETag": etag,
            "Cache-Control": cache_control,
        },
    )
