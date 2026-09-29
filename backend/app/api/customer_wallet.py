"""Customer wallet endpoints for loyalty card and transaction history management."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.entities import User
from app.schemas.wallet import (
    CustomerCardResponse,
    CustomerTransactionHistoryResponse,
)
from app.services.wallet_service import (
    auto_bind_cards_by_phone,
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
