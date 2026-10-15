import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.phone import normalize_phone
from app.core.security import create_access_token, hash_refresh_token
from app.core.time import utcnow
from app.models.entities import AuthSession, Business, Card, User, UserCard


@pytest.mark.asyncio
async def test_auto_bind_multi_business(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Unbound cards across different businesses matching user phone are auto-bound on GET /me/cards."""
    # 1. Create two businesses
    biz1 = Business(name="Supermarket A")
    biz2 = Business(name="Fashion Store B")
    db_session.add_all([biz1, biz2])
    await db_session.flush()

    # 2. Create cards for both businesses with same phone
    user_phone = "+77015550011"
    card1 = Card(
        business_id=biz1.id,
        barcode="0123456789011",
        phone=user_phone,
        balance=Decimal("100.0000"),
    )
    card2 = Card(
        business_id=biz2.id,
        barcode="0123456789012",
        phone=user_phone,
        balance=Decimal("200.0000"),
    )
    db_session.add_all([card1, card2])

    # 3. Create customer user without prior card bindings
    user = User(phone=user_phone, language="ru")
    db_session.add(user)
    await db_session.flush()

    auth_session = AuthSession(
        user_id=user.id,
        device_id="test-device",
        refresh_token_hash=hash_refresh_token(f"rfr_{uuid.uuid4()}"),
        expires_at=utcnow() + timedelta(days=30),
    )
    db_session.add(auth_session)
    await db_session.commit()

    token = create_access_token(user_id=user.id, session_id=auth_session.id)

    # 4. Call GET /me/cards
    response = await client.get(
        "/me/cards",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    barcodes = {c["barcode"] for c in data}
    assert barcodes == {"0123456789011", "0123456789012"}

    # 5. Check user_cards table bindings
    bindings = (
        await db_session.scalars(
            select(UserCard).where(UserCard.user_id == user.id)
        )
    ).all()
    assert len(bindings) == 2
    assert all(b.bind_method == "phone_auto" for b in bindings)


@pytest.mark.asyncio
async def test_auto_bind_does_not_unhide_soft_hidden_card(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """A card previously hidden by customer must NOT be unhidden by subsequent auto-bind."""
    biz = Business(name="Electronics C")
    db_session.add(biz)
    await db_session.flush()

    user_phone = "+77015550022"
    card = Card(
        business_id=biz.id,
        barcode="0123456789022",
        phone=user_phone,
        balance=Decimal("500.0000"),
    )
    db_session.add(card)

    user = User(phone=user_phone, language="ru")
    db_session.add(user)
    await db_session.flush()

    # Pre-bind and mark as hidden
    user_card = UserCard(
        user_id=user.id,
        card_id=card.id,
        bind_method="phone_auto",
        hidden_at=utcnow(),
    )
    db_session.add(user_card)

    auth_session = AuthSession(
        user_id=user.id,
        device_id="test-device",
        refresh_token_hash=hash_refresh_token(f"rfr_{uuid.uuid4()}"),
        expires_at=utcnow() + timedelta(days=30),
    )
    db_session.add(auth_session)
    await db_session.commit()

    token = create_access_token(user_id=user.id, session_id=auth_session.id)

    # Calling GET /me/cards triggers auto_bind
    response = await client.get(
        "/me/cards",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json() == []

    # Card remains hidden in database
    refreshed_uc = await db_session.get(UserCard, user_card.id)
    assert refreshed_uc is not None
    assert refreshed_uc.hidden_at is not None


@pytest.mark.asyncio
async def test_auto_bind_cross_user_isolation(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """If a card is already bound to User A, User B's auto-bind must NOT steal or rebind it."""
    biz = Business(name="Exclusive Store")
    db_session.add(biz)
    await db_session.flush()

    card_phone = "+77015550033"
    card = Card(
        business_id=biz.id,
        barcode="0123456789033",
        phone=card_phone,
        balance=Decimal("700.0000"),
    )
    db_session.add(card)

    # Distinct users with distinct phone numbers
    user_a = User(phone="+77011110033", language="ru")
    user_b = User(phone=card_phone, language="en")
    db_session.add_all([user_a, user_b])
    await db_session.flush()

    # Card is bound to User A (e.g. from earlier binding)
    uc_a = UserCard(user_id=user_a.id, card_id=card.id, bind_method="phone_auto")
    db_session.add(uc_a)

    auth_b = AuthSession(
        user_id=user_b.id,
        device_id="device-b",
        refresh_token_hash=hash_refresh_token(f"rfr_{uuid.uuid4()}"),
        expires_at=utcnow() + timedelta(days=30),
    )
    db_session.add(auth_b)
    await db_session.commit()

    token_b = create_access_token(user_id=user_b.id, session_id=auth_b.id)

    # User B calls GET /me/cards
    response = await client.get(
        "/me/cards",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 200
    assert response.json() == []

    # Verify User A is still the sole owner
    bindings = (
        await db_session.scalars(
            select(UserCard).where(UserCard.card_id == card.id)
        )
    ).all()
    assert len(bindings) == 1
    assert bindings[0].user_id == user_a.id


@pytest.mark.asyncio
async def test_auto_bind_phone_normalization(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Card with +7 (701) 123-45-67 is linked to User with 87011234567."""
    biz = Business(name="Telecom")
    db_session.add(biz)
    await db_session.flush()

    card = Card(
        business_id=biz.id,
        barcode="0123456789044",
        phone=normalize_phone("+7 (701) 123-45-67"),
        balance=Decimal("350.0000"),
    )
    db_session.add(card)

    user = User(phone=normalize_phone("8 (701) 123-45-67"), language="ru")
    db_session.add(user)
    await db_session.flush()

    auth = AuthSession(
        user_id=user.id,
        device_id="device-tel",
        refresh_token_hash=hash_refresh_token(f"rfr_{uuid.uuid4()}"),
        expires_at=utcnow() + timedelta(days=30),
    )
    db_session.add(auth)
    await db_session.commit()

    token = create_access_token(user_id=user.id, session_id=auth.id)

    response = await client.get(
        "/me/cards",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["barcode"] == "0123456789044"


@pytest.mark.asyncio
async def test_auto_bind_ten_digit_card_phone(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Card phone entered in ONE without trunk prefix (701 123 45 67) binds to +77011234567."""
    biz = Business(name="Bakery")
    db_session.add(biz)
    await db_session.flush()

    card = Card(
        business_id=biz.id,
        barcode="0123456789055",
        phone=normalize_phone("701 123 45 67"),
        balance=Decimal("120.0000"),
    )
    db_session.add(card)

    user = User(phone="+77011234567", language="ru")
    db_session.add(user)
    await db_session.flush()

    auth = AuthSession(
        user_id=user.id,
        device_id="device-bakery",
        refresh_token_hash=hash_refresh_token(f"rfr_{uuid.uuid4()}"),
        expires_at=utcnow() + timedelta(days=30),
    )
    db_session.add(auth)
    await db_session.commit()

    token = create_access_token(user_id=user.id, session_id=auth.id)

    response = await client.get(
        "/me/cards",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["barcode"] == "0123456789055"


@pytest.mark.asyncio
async def test_auto_bind_pii_not_in_logs(
    client: AsyncClient,
    db_session: AsyncSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Auto-bind conflict warning must NOT log user phone, full_name, or user IDs."""
    import logging

    biz = Business(name="Security Test Store")
    db_session.add(biz)
    await db_session.flush()

    conflict_phone = "+77019998877"
    card = Card(
        business_id=biz.id,
        barcode="0123456789099",
        phone=conflict_phone,
        balance=Decimal("150.0000"),
    )
    db_session.add(card)

    user_a = User(phone="+77011112233", language="ru")
    user_b = User(phone=conflict_phone, language="en")
    db_session.add_all([user_a, user_b])
    await db_session.flush()

    # Pre-bind to User A
    uc_a = UserCard(user_id=user_a.id, card_id=card.id, bind_method="phone_auto")
    db_session.add(uc_a)

    auth_b = AuthSession(
        user_id=user_b.id,
        device_id="device-pii",
        refresh_token_hash=hash_refresh_token(f"rfr_{uuid.uuid4()}"),
        expires_at=utcnow() + timedelta(days=30),
    )
    db_session.add(auth_b)
    await db_session.commit()

    token_b = create_access_token(user_id=user_b.id, session_id=auth_b.id)

    with caplog.at_level(logging.WARNING):
        resp = await client.get(
            "/me/cards",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp.status_code == 200

    # Ensure warning was logged
    warning_logs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("Auto-bind skipped because candidate card" in msg for msg in warning_logs)

    # STRICT PII ASSERTIONS:
    # 1. Full phone must NOT appear in any log
    assert conflict_phone not in caplog.text
    assert "+770" not in caplog.text
    assert "77019998877" not in caplog.text
    # 2. User IDs must NOT appear in any log
    assert str(user_b.id) not in caplog.text
    assert str(user_a.id) not in caplog.text
    # 3. Tokens must NOT appear in log
    assert token_b not in caplog.text

