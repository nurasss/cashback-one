import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_refresh_token
from app.core.time import utcnow
from app.models.entities import AuthSession, Business, Card, Transaction, User, UserCard


async def seed_user_with_card(
    db_session: AsyncSession,
    phone: str = "+77019998877",
    balance: Decimal = Decimal("1250.5000"),
    business_name: str = "Magnum Cash&Carry",
) -> tuple[User, str, Card, Business]:
    """Helper fixture to create a business, card, customer user, and binding."""
    business = Business(
        name=business_name,
        logo_url="https://cdn.example.com/logo.png",
        colors={
            "primary_color": "#FF0000",
            "accent_color": "#00FF00",
        },
    )
    db_session.add(business)
    await db_session.flush()

    card = Card(
        business_id=business.id,
        barcode=f"CARD-{uuid.uuid4().hex[:8].upper()}",
        phone=phone,
        balance=balance,
        is_blocked=False,
    )
    db_session.add(card)

    user = User(phone=phone, language="ru")
    db_session.add(user)
    await db_session.flush()

    user_card = UserCard(
        user_id=user.id,
        card_id=card.id,
        bind_method="phone_auto",
    )
    db_session.add(user_card)

    auth_session = AuthSession(
        user_id=user.id,
        device_id="test-device-uuid",
        refresh_token_hash=hash_refresh_token(f"rfr_{uuid.uuid4()}"),
        expires_at=utcnow() + timedelta(days=30),
    )
    db_session.add(auth_session)
    await db_session.commit()

    token = create_access_token(user_id=user.id, session_id=auth_session.id)
    return user, token, card, business


@pytest.mark.asyncio
async def test_get_customer_cards_list(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /me/cards returns cards with 4-decimal balance strings and branding."""
    _user, token, card, business = await seed_user_with_card(
        db_session, balance=Decimal("1250.5000")
    )

    response = await client.get(
        "/me/cards",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    item = data[0]

    assert item["id"] == str(card.id)
    assert item["barcode"] == card.barcode
    assert item["balance"] == "1250.5000"
    assert isinstance(item["balance"], str)
    assert item["is_blocked"] is False
    assert item["bind_method"] == "phone_auto"
    assert item["business"]["id"] == str(business.id)
    assert item["business"]["name"] == "Magnum Cash&Carry"
    assert item["business"]["branding"]["logo_url"] == "https://cdn.example.com/logo.png"
    assert item["business"]["branding"]["primary_color"] == "#FF0000"
    assert item["business"]["branding"]["accent_color"] == "#00FF00"


@pytest.mark.asyncio
async def test_get_customer_card_detail(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /me/cards/{id} returns single card detail."""
    _user, token, card, business = await seed_user_with_card(db_session)

    response = await client.get(
        f"/me/cards/{card.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(card.id)
    assert data["barcode"] == card.barcode
    assert data["business"]["name"] == business.name


@pytest.mark.asyncio
async def test_get_card_detail_idor_protection(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """User B cannot view User A's card; receives uniform 404 without data leak."""
    _user_a, _token_a, card_a, _ = await seed_user_with_card(
        db_session, phone="+77011111111", business_name="Store A"
    )
    _, token_b, _, _ = await seed_user_with_card(
        db_session, phone="+77012222222", business_name="Store B"
    )

    # User B requests User A's card
    response = await client.get(
        f"/me/cards/{card_a.id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CARD_NOT_FOUND"


@pytest.mark.asyncio
async def test_soft_hide_card(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """DELETE /me/cards/{id} soft-hides card; preserves card entity in cards table."""
    _user, token, card, _ = await seed_user_with_card(db_session)

    # 1. Delete card
    delete_resp = await client.delete(
        f"/me/cards/{card.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_resp.status_code == 204

    # 2. Subsequent GET /me/cards does not return the hidden card
    list_resp = await client.get(
        "/me/cards",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_resp.status_code == 200
    assert list_resp.json() == []

    # 3. Subsequent GET /me/cards/{id} returns 404
    detail_resp = await client.get(
        f"/me/cards/{card.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail_resp.status_code == 404

    # 4. Underlying card in cards table is NOT deleted or altered
    raw_card = await db_session.get(Card, card.id)
    assert raw_card is not None
    assert raw_card.balance == Decimal("1250.5000")
    assert raw_card.is_blocked is False

    # 5. Repeated DELETE returns 404
    repeat_delete = await client.delete(
        f"/me/cards/{card.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert repeat_delete.status_code == 404


@pytest.mark.asyncio
async def test_card_transaction_history_pagination(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Transaction history supports cursor-based pagination and 4-decimal formatting."""
    _, token, card, _ = await seed_user_with_card(db_session)

    base_time = utcnow()
    # Create 5 transactions spaced by minutes
    for i in range(5):
        tx = Transaction(
            card_id=card.id,
            external_id=f"tx-ext-{i}",
            type="accrual" if i % 2 == 0 else "redemption",
            amount=Decimal(f"{100 + i * 10}.5000"),
            balance_after=Decimal(f"{1000 + i * 50}.0000"),
            occurred_at=base_time + timedelta(minutes=i),
            receipt_ref=f"REC-{i}",
            store="Branch 1",
        )
        db_session.add(tx)
    await db_session.commit()

    # Page 1: limit 2
    resp1 = await client.get(
        f"/me/cards/{card.id}/transactions?limit=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert len(data1["items"]) == 2
    assert data1["has_more"] is True
    assert data1["next_cursor"] is not None
    # Latest transaction first (i=4)
    assert data1["items"][0]["external_id"] == "tx-ext-4"
    assert data1["items"][0]["amount"] == "140.5000"
    assert isinstance(data1["items"][0]["amount"], str)
    assert data1["items"][0]["balance_after"] == "1200.0000"

    cursor1 = data1["next_cursor"]

    # Page 2: limit 2 with cursor
    resp2 = await client.get(
        f"/me/cards/{card.id}/transactions?limit=2&cursor={cursor1}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert len(data2["items"]) == 2
    assert data2["has_more"] is True
    assert data2["items"][0]["external_id"] == "tx-ext-2"

    cursor2 = data2["next_cursor"]

    # Page 3: last page
    resp3 = await client.get(
        f"/me/cards/{card.id}/transactions?limit=2&cursor={cursor2}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp3.status_code == 200
    data3 = resp3.json()
    assert len(data3["items"]) == 1
    assert data3["has_more"] is False
    assert data3["next_cursor"] is None
    assert data3["items"][0]["external_id"] == "tx-ext-0"


@pytest.mark.asyncio
async def test_card_transaction_type_filter(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Transaction query filters by transaction type."""
    _, token, card, _ = await seed_user_with_card(db_session)
    base_time = utcnow()

    tx1 = Transaction(
        card_id=card.id,
        external_id="tx-accrual-1",
        type="accrual",
        amount=Decimal("50.0000"),
        balance_after=Decimal("150.0000"),
        occurred_at=base_time,
    )
    tx2 = Transaction(
        card_id=card.id,
        external_id="tx-redemption-1",
        type="redemption",
        amount=Decimal("30.0000"),
        balance_after=Decimal("120.0000"),
        occurred_at=base_time + timedelta(minutes=1),
    )
    db_session.add_all([tx1, tx2])
    await db_session.commit()

    # Filter for redemption only
    resp = await client.get(
        f"/me/cards/{card.id}/transactions?type=redemption",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["external_id"] == "tx-redemption-1"
    assert items[0]["type"] == "redemption"


@pytest.mark.asyncio
async def test_card_transactions_idor_protection(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """User B cannot fetch transactions for User A's card (returns 404)."""
    _, _, card_a, _ = await seed_user_with_card(
        db_session, phone="+77013334455", business_name="Store A"
    )
    _, token_b, _, _ = await seed_user_with_card(
        db_session, phone="+77015556677", business_name="Store B"
    )

    response = await client.get(
        f"/me/cards/{card_a.id}/transactions",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CARD_NOT_FOUND"


@pytest.mark.asyncio
async def test_card_transactions_invalid_cursor(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Corrupt or non-base64 cursor returns 400 INVALID_CURSOR."""
    _, token, card, _ = await seed_user_with_card(db_session)

    response = await client.get(
        f"/me/cards/{card.id}/transactions?cursor=totally-invalid-garbage-cursor",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CURSOR"


@pytest.mark.asyncio
async def test_card_transactions_invalid_limit(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Limit < 1 or > 100 is rejected with 422."""
    _, token, card, _ = await seed_user_with_card(db_session)

    resp_zero = await client.get(
        f"/me/cards/{card.id}/transactions?limit=0",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_zero.status_code == 422

    resp_high = await client.get(
        f"/me/cards/{card.id}/transactions?limit=101",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_high.status_code == 422
