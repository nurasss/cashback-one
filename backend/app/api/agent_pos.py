"""POS-facing endpoints authenticated by the business agent key (X-Agent-Key)."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.entities import Agent
from app.schemas.pos import (
    QrResolveRequest,
    QrResolveResponse,
    RedemptionRequest,
    RedemptionRequestResponse,
    RedemptionVerifyRequest,
    RedemptionVerifyResponse,
)
from app.services.agent_auth import authenticate_agent
from app.services.rate_limiter import RateLimiter, get_rate_limiter
from app.services.redemption_service import request_redemption, resolve_card, verify_redemption
from app.services.whatsapp_sender import WhatsAppSender, get_whatsapp_sender

router = APIRouter(prefix="/agent", tags=["Agent POS"])


@router.post("/qr/resolve", response_model=QrResolveResponse)
async def resolve_qr(
    body: QrResolveRequest,
    agent: Annotated[Agent, Depends(authenticate_agent)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> QrResolveResponse:
    """Turn a scanned dynamic QR token into the card barcode for this business."""
    card = await resolve_card(session, agent, None, body.token)
    return QrResolveResponse(card_id=card.id, barcode=card.barcode)


@router.post("/redemptions", response_model=RedemptionRequestResponse, status_code=201)
async def create_redemption(
    body: RedemptionRequest,
    agent: Annotated[Agent, Depends(authenticate_agent)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    sender: Annotated[WhatsAppSender, Depends(get_whatsapp_sender)],
) -> RedemptionRequestResponse:
    """Send a write-off confirmation code to the customer's WhatsApp."""
    return await request_redemption(session, agent, body, limiter, sender)


@router.post("/redemptions/{redemption_id}/verify", response_model=RedemptionVerifyResponse)
async def confirm_redemption(
    redemption_id: uuid.UUID,
    body: RedemptionVerifyRequest,
    agent: Annotated[Agent, Depends(authenticate_agent)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RedemptionVerifyResponse:
    """Check the code the customer read out; on success the POS posts the write-off in ONE."""
    return await verify_redemption(session, agent, redemption_id, body.code)
