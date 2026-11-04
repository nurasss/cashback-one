"""POS cash register direct cloud endpoints authenticated by X-Pos-Key."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.entities import PosKey
from app.schemas.pos import (
    PosRedemptionRequest,
    PosRedemptionResponse,
    PosRedemptionVerifyRequest,
    RedemptionVerifyResponse,
)
from app.services.pos_auth import authenticate_pos_key
from app.services.pos_service import request_pos_redemption, verify_pos_redemption
from app.services.push_sender import PushSender, get_push_sender
from app.services.rate_limiter import RateLimiter, get_rate_limiter

router = APIRouter(prefix="/pos", tags=["POS"])


@router.post("/redemptions", response_model=PosRedemptionResponse, status_code=201)
async def create_pos_redemption(
    body: PosRedemptionRequest,
    pos_key: Annotated[PosKey, Depends(authenticate_pos_key)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    sender: Annotated[PushSender, Depends(get_push_sender)],
) -> PosRedemptionResponse:
    """Request a write-off confirmation code delivered to the customer via push notification."""
    return await request_pos_redemption(session, pos_key, body, limiter, sender)


@router.post("/redemptions/{redemption_id}/verify", response_model=RedemptionVerifyResponse)
async def confirm_pos_redemption(
    redemption_id: uuid.UUID,
    body: PosRedemptionVerifyRequest,
    pos_key: Annotated[PosKey, Depends(authenticate_pos_key)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RedemptionVerifyResponse:
    """Verify the 4-digit code entered by the cashier."""
    return await verify_pos_redemption(session, pos_key, redemption_id, body.code)
