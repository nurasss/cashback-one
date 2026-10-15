"""Customer wallet endpoints for loyalty card and transaction history management."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.errors import AppError
from app.db.session import get_session
from app.models.entities import User
from app.schemas.wallet import (
    BindCardRequest,
    CustomerCardResponse,
    CustomerTransactionHistoryResponse,
)
from app.services.rate_limiter import RateLimiter, get_rate_limiter
from app.services.wallet_service import (
    auto_bind_cards_by_phone,
    bind_customer_card,
    get_customer_card_detail,
    get_customer_card_transactions,
    get_customer_cards,
    hide_customer_card,
)

router = APIRouter(prefix="/me", tags=["Customer Wallet"])


@router.get("/cards", response_model=list[CustomerCardResponse])
async def list_cards(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[CustomerCardResponse]:
    """Retrieve customer's loyalty cards.

    Automatically triggers phone-based card discovery and binding on access.
    """
    await auto_bind_cards_by_phone(session, current_user)
    await session.commit()
    return await get_customer_cards(session, current_user.id)


@router.post(
    "/cards/bind",
    response_model=CustomerCardResponse,
    status_code=status.HTTP_200_OK,
)
async def bind_card(
    body: BindCardRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> CustomerCardResponse:
    """Manually bind an existing loyalty card via barcode or scanned QR.

    Requires phone ownership match. Idempotent for existing visible bindings,
    and explicitly unhides previously soft-hidden bindings owned by the customer.
    Rate limited per customer to prevent barcode enumeration.
    """
    if await limiter.is_rate_limited(
        f"bind:{current_user.id}",
        settings.card_bind_user_limit,
        settings.card_bind_rate_window_seconds,
    ):
        raise AppError(
            code="RATE_LIMIT_EXCEEDED",
            message="Too many card link attempts. Please try again later.",
            status_code=429,
        )
    return await bind_customer_card(
        session=session,
        user=current_user,
        barcode=body.barcode,
        business_id=body.business_id,
    )


@router.get("/cards/{card_id}", response_model=CustomerCardResponse)
async def get_card(
    card_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CustomerCardResponse:
    """Retrieve details for a single loyalty card in customer's wallet.

    Returns 404 if the card is not found or not owned by the user.
    """
    return await get_customer_card_detail(session, current_user.id, card_id)


@router.delete(
    "/cards/{card_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_card(
    card_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """Soft-hide a loyalty card from customer's wallet view.

    The underlying card record and mirror data are preserved.
    Returns 404 if the card is not found or not owned by the user.
    """
    await hide_customer_card(session, current_user.id, card_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/cards/{card_id}/transactions",
    response_model=CustomerTransactionHistoryResponse,
)
async def list_card_transactions(
    card_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query()] = None,
    type: Annotated[str | None, Query()] = None,
) -> CustomerTransactionHistoryResponse:
    """Retrieve deterministic cursor-paginated transaction history for a card.

    type performs exact filtering by the canonical type received from ONE.
    Returns 404 if the card is not found or not owned by the user.
    """
    return await get_customer_card_transactions(
        session,
        current_user.id,
        card_id,
        limit=limit,
        cursor=cursor,
        tx_type=type,
    )
