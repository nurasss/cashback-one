"""Customer app endpoints: profile, promotions, notifications, badges, dynamic card QR and wallet passes."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
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
from app.services.qr_tokens import issue_card_token

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
