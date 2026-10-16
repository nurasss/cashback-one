"""Public wallet endpoints: Apple pass download by signed link and the pass logo for Google Wallet."""
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.session import get_session
from app.models.entities import Business, Card
from app.services import wallet_passes

router = APIRouter(prefix="/wallet", tags=["Wallet"])


@router.get("/apple/{token}.pkpass", response_class=Response)
async def apple_pass(token: str, session: Annotated[AsyncSession, Depends(get_session)]) -> Response:
    if not wallet_passes.apple_enabled():
        raise AppError("WALLET_UNAVAILABLE", "Apple Wallet is not configured", 503)
    card_id = wallet_passes.verify_link_token(token)
    if card_id is None:
        raise AppError("WALLET_LINK_INVALID", "Link is invalid or expired", 404)
    row = (await session.execute(
        select(Card, Business).join(Business, Business.id == Card.business_id)
        .where(Card.id == card_id, Business.status == "active", Card.is_blocked.is_(False))
    )).first()
    if row is None:
        raise AppError("WALLET_LINK_INVALID", "Link is invalid or expired", 404)
    return Response(
        content=wallet_passes.build_apple_pass(row[0], row[1]),
        media_type="application/vnd.apple.pkpass",
        headers={"Content-Disposition": 'attachment; filename="card.pkpass"', "Cache-Control": "no-store"},
    )


@router.get("/assets/google-logo.png", response_class=Response)
async def google_logo() -> Response:
    return Response(
        content=(wallet_passes.ASSETS / wallet_passes.GOOGLE_LOGO).read_bytes(),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )
