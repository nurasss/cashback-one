"""Customer app endpoints: profile, promotions, notifications, badges, dynamic card QR and wallet passes."""
import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings, settings
from app.core.errors import AppError
from app.db.session import get_session
from app.models.entities import Business, Card, User, UserCard
from app.schemas.customer_app import (
    BadgesResponse,
    CardQrResponse,
    NotificationsResponse,
    ProfileResponse,
    ProfileUpdateRequest,
    PromotionItem,
    PromotionsResponse,
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
) -> PromotionsResponse:
    return await content_service.list_promotions(session, current_user)


@router.post("/promotions/seen", status_code=status.HTTP_204_NO_CONTENT)
async def promotions_seen(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    await content_service.mark_promotions_seen(session, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/promotions/{promotion_id}", response_model=PromotionItem)
async def promotion_detail(
    promotion_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PromotionItem:
    return await content_service.get_promotion(session, current_user, promotion_id)


@router.get("/notifications", response_model=NotificationsResponse)
async def notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> NotificationsResponse:
    return await content_service.list_notifications(session, current_user)


@router.post("/notifications/read", status_code=status.HTTP_204_NO_CONTENT)
async def notifications_read(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    await content_service.mark_notifications_read(session, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/badges", response_model=BadgesResponse)
async def badges(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> BadgesResponse:
    return await content_service.badges(session, current_user)


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
