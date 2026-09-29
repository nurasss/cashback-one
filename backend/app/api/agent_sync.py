from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.core.phone import normalize_phone
from app.core.time import as_utc, utcnow
from app.db.session import get_session
from app.models.entities import Agent, Business, Card, Transaction
from app.schemas.agent_sync import (
    CardsSyncRequest,
    CardsSyncResponse,
    HeartbeatRequest,
    HeartbeatResponse,
    TransactionsSyncRequest,
    TransactionsSyncResponse,
)
from app.services.agent_auth import authenticate_agent

router = APIRouter(prefix="/agent", tags=["Agent Sync"])


@router.post("/sync/cards", response_model=CardsSyncResponse)
async def sync_cards(
    body: CardsSyncRequest,
    agent: Annotated[Agent, Depends(authenticate_agent)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CardsSyncResponse:
    """Ingest card mirror batch from ONE Agent.

    Enforces tenant isolation (business_id resolved from authenticated agent),
    database-level atomic serialization per tenant, stale data protection,
    phone normalization, and batch limits.
    """
    if len(body.cards) > settings.sync_max_cards_batch:
        raise AppError(
            code="SYNC_BATCH_TOO_LARGE",
            message=f"Cards batch exceeds maximum limit of {settings.sync_max_cards_batch} items",
            status_code=422,
        )

    # Validate phones upfront
    normalized_phones: list[str | None] = []
    for item in body.cards:
        if item.phone is not None:
            try:
                normalized_phones.append(normalize_phone(item.phone))
            except ValueError as err:
                raise AppError(
                    code="INVALID_PHONE_FORMAT",
                    message=f"Card '{item.barcode}' has invalid phone: {err}",
                    status_code=422,
                ) from err
        else:
            normalized_phones.append(None)

    # Acquire tenant-level transaction lock to serialize concurrent syncs for this business
    await session.execute(
        select(Business.id).where(Business.id == agent.business_id).with_for_update()
    )

    barcodes = [c.barcode for c in body.cards]
    existing_cards_stmt = select(Card).where(
        Card.business_id == agent.business_id,
        Card.barcode.in_(barcodes),
    )

    existing_cards = {
        c.barcode: c for c in (await session.scalars(existing_cards_stmt)).all()
    }

    created = 0
    updated = 0
    ignored_stale = 0

    for item, norm_phone in zip(body.cards, normalized_phones, strict=True):
        if item.barcode in existing_cards:
            existing = existing_cards[item.barcode]
            # Stale data protection: if incoming snapshot timestamp is older or equal, ignore
            if as_utc(item.updated_at) <= as_utc(existing.updated_at):
                ignored_stale += 1
            else:
                existing.phone = norm_phone
                existing.full_name = item.full_name
                existing.balance = item.balance
                existing.is_blocked = item.is_blocked
                existing.updated_at = item.updated_at
                updated += 1
        else:
            new_card = Card(
                business_id=agent.business_id,
                barcode=item.barcode,
                phone=norm_phone,
                full_name=item.full_name,
                balance=item.balance,
                is_blocked=item.is_blocked,
                updated_at=item.updated_at,
            )
            session.add(new_card)
            # Track in map to handle duplicate barcodes within the same batch safely
            existing_cards[item.barcode] = new_card
            created += 1

    await session.commit()

    return CardsSyncResponse(
        received=len(body.cards),
        created=created,
        updated=updated,
        ignored_stale=ignored_stale,
    )


@router.post("/sync/transactions", response_model=TransactionsSyncResponse)
async def sync_transactions(
    body: TransactionsSyncRequest,
    agent: Annotated[Agent, Depends(authenticate_agent)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TransactionsSyncResponse:
    """Ingest bonus transactions batch from ONE Agent.

    Enforces tenant isolation, idempotency on (card_id, external_id),
    unknown card rejection, and batch limits.
    """
    if len(body.transactions) > settings.sync_max_transactions_batch:
        raise AppError(
            code="SYNC_BATCH_TOO_LARGE",
            message=(
                f"Transactions batch exceeds maximum limit of "
                f"{settings.sync_max_transactions_batch} items"
            ),
            status_code=422,
        )

    # Acquire tenant-level transaction lock to serialize concurrent syncs for this business
    await session.execute(
        select(Business.id).where(Business.id == agent.business_id).with_for_update()
    )

    # Resolve cards strictly within authenticated agent's business_id
    barcodes = list({t.barcode for t in body.transactions})
    cards_stmt = select(Card).where(
        Card.business_id == agent.business_id,
        Card.barcode.in_(barcodes),
    )
    cards_map = {c.barcode: c for c in (await session.scalars(cards_stmt)).all()}

    # Unknown card validation: reject batch if any card does not exist for this business
    for item in body.transactions:
        if item.barcode not in cards_map:
            raise AppError(
                code="UNKNOWN_CARD_FOR_TRANSACTION",
                message=(
                    f"Card with barcode '{item.barcode}' does not exist for authenticated business. "
                    f"Cards must be synchronized before transactions."
                ),
                status_code=422,
            )


    # Check existing transactions for idempotency
    card_ids = [cards_map[t.barcode].id for t in body.transactions]
    external_ids = [t.external_id for t in body.transactions]
    existing_txs_stmt = select(Transaction.card_id, Transaction.external_id).where(
        Transaction.card_id.in_(card_ids),
        Transaction.external_id.in_(external_ids),
    )
    existing_keys = {
        (row[0], row[1]) for row in (await session.execute(existing_txs_stmt)).all()
    }

    created = 0
    duplicates = 0

    for item in body.transactions:
        card = cards_map[item.barcode]
        key = (card.id, item.external_id)

        if key in existing_keys:
            duplicates += 1
        else:
            new_tx = Transaction(
                card_id=card.id,
                external_id=item.external_id,
                type=item.type,
                amount=item.amount,
                balance_after=item.balance_after,
                occurred_at=item.occurred_at,
                receipt_ref=item.receipt_ref,
                store=item.store,
            )
            session.add(new_tx)
            # Track key to avoid duplicates within the same incoming batch
            existing_keys.add(key)
            created += 1

    await session.commit()

    return TransactionsSyncResponse(
        received=len(body.transactions),
        created=created,
        duplicates=duplicates,
    )


@router.post("/heartbeat", response_model=HeartbeatResponse)
async def agent_heartbeat(
    body: HeartbeatRequest,
    agent: Annotated[Agent, Depends(authenticate_agent)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> HeartbeatResponse:
    """Record agent heartbeat.

    Server controls last_seen_at using server UTC time.
    Updates agent version, last reported sync time, and last error.
    """
    agent.last_seen_at = utcnow()
    if body.version is not None:
        agent.version = body.version
    agent.last_sync_at = body.last_successful_sync_at
    agent.last_error = body.error

    await session.commit()
    return HeartbeatResponse(status="ok")
