"""Tests for manual QR/barcode card binding (POST /me/cards/bind)."""
import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_refresh_token
from app.core.time import utcnow
from app.models.entities import AuthSession, Business, Card, User, UserCard


async def create_test_customer(
    db_session: AsyncSession,
    phone: str = "+77019998877",
) -> tuple[User, str]:
    """Create a verified test customer with active auth session."""
    user = User(phone=phone, language="ru")
    db_session.add(user)
    await db_session.flush()

    auth_session = AuthSession(
        user_id=user.id,
        device_id="test-device-uuid",
        refresh_token_hash=hash_refresh_token(f"rfr_{uuid.uuid4()}"),
        expires_at=utcnow() + timedelta(days=30),
    )
    db_session.add(auth_session)
    await db_session.commit()

    token = create_access_token(user_id=user.id, session_id=auth_session.id)
    return user, token


@pytest.mark.asyncio
async def test_bind_card_barcode_validation(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test 13-digit barcode validation: length, types, spaces, leading zeros."""
    _, token = await create_test_customer(db_session)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. 12 digits rejected
    resp = await client.post("/me/cards/bind", json={"barcode": "012345678901"}, headers=headers)
    assert resp.status_code == 422

    # 2. 14 digits rejected
    resp = await client.post("/me/cards/bind", json={"barcode": "01234567890123"}, headers=headers)
    assert resp.status_code == 422

    # 3. Letters rejected
    resp = await client.post("/me/cards/bind", json={"barcode": "012345678901A"}, headers=headers)
    assert resp.status_code == 422

    # 4. Internal spaces rejected
    resp = await client.post("/me/cards/bind", json={"barcode": "0123 45678901"}, headers=headers)
    assert resp.status_code == 422

    # 5. Non-string integer rejected
    resp = await client.post("/me/cards/bind", json={"barcode": 1234567890123}, headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_bind_card_outer_whitespace_trimmed(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Outer whitespace is trimmed and valid leading zero barcode succeeds."""
    _, token = await create_test_customer(db_session, phone="+77011112233")
    headers = {"Authorization": f"Bearer {token}"}

    business = Business(name="Magnum", barcode_prefixes=["012"], status="active")
    db_session.add(business)
    await db_session.flush()

    card = Card(
        business_id=business.id,
        barcode="0123456789012",
        phone="+77011112233",
        balance=Decimal("200.0000"),
        is_blocked=False,
    )
    db_session.add(card)
    await db_session.commit()

    resp = await client.post(
        "/me/cards/bind",
        json={"barcode": "  0123456789012  "},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["barcode"] == "0123456789012"
    assert data["id"] == str(card.id)
    assert data["bind_method"] == "manual_barcode"


@pytest.mark.asyncio
async def test_bind_card_not_found(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Card not in mirror or business mismatch returns 404 CARD_NOT_FOUND."""
    _, token = await create_test_customer(db_session)
    headers = {"Authorization": f"Bearer {token}"}

    # Nonexistent barcode
    resp = await client.post("/me/cards/bind", json={"barcode": "9999999999999"}, headers=headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CARD_NOT_FOUND"

    # Business provided but wrong
    random_biz_id = str(uuid.uuid4())
    resp = await client.post(
        "/me/cards/bind",
        json={"barcode": "9999999999999", "business_id": random_biz_id},
        headers=headers,
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CARD_NOT_FOUND"


@pytest.mark.asyncio
async def test_bind_card_inactive_business_ignored(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Cards from inactive business return 404 CARD_NOT_FOUND (neutral error)."""
    _, token = await create_test_customer(db_session, phone="+77015554433")
    headers = {"Authorization": f"Bearer {token}"}

    business = Business(name="Inactive Shop", status="inactive")
    db_session.add(business)
    await db_session.flush()

    card = Card(
        business_id=business.id,
        barcode="0987654321098",
        phone="+77015554433",
        balance=Decimal("100.0000"),
    )
    db_session.add(card)
    await db_session.commit()

    resp = await client.post(
        "/me/cards/bind",
        json={"barcode": "0987654321098", "business_id": str(business.id)},
        headers=headers,
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CARD_NOT_FOUND"


@pytest.mark.asyncio
async def test_bind_card_business_resolution_prefix_unique(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Same barcode across 2 businesses: prefix resolves Business A unambiguously."""
    _, token = await create_test_customer(db_session, phone="+77017778899")
    headers = {"Authorization": f"Bearer {token}"}

    barcode = "0123456789012"

    biz_a = Business(name="Business A", barcode_prefixes=["012"], status="active")
    biz_b = Business(name="Business B", barcode_prefixes=["777"], status="active")
    db_session.add_all([biz_a, biz_b])
    await db_session.flush()

    card_a = Card(
        business_id=biz_a.id,
        barcode=barcode,
        phone="+77017778899",
        balance=Decimal("500.0000"),
    )
    card_b = Card(
        business_id=biz_b.id,
        barcode=barcode,
        phone="+77017778899",
        balance=Decimal("900.0000"),
    )
    db_session.add_all([card_a, card_b])
    await db_session.commit()

    # Omit business_id: prefix "012" matches biz_a
    resp = await client.post("/me/cards/bind", json={"barcode": barcode}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(card_a.id)
    assert data["business"]["id"] == str(biz_a.id)


@pytest.mark.asyncio
async def test_bind_card_business_selection_required_ambiguous_prefix(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Same barcode across 2 businesses with identical prefix requires selection."""
    _, token = await create_test_customer(db_session, phone="+77017778899")
    headers = {"Authorization": f"Bearer {token}"}

    barcode = "0123456789012"

    biz_a = Business(
        name="Alpha Mall",
        logo_url="https://cdn.example.com/alpha.png",
        colors={"primary_color": "#111111"},
        barcode_prefixes=["012"],
        status="active",
    )
    biz_b = Business(
        name="Beta Store",
        logo_url="https://cdn.example.com/beta.png",
        colors={"primary_color": "#222222"},
        barcode_prefixes=["012"],
        status="active",
    )
    db_session.add_all([biz_a, biz_b])
    await db_session.flush()

    card_a = Card(business_id=biz_a.id, barcode=barcode, phone="+77017778899")
    card_b = Card(business_id=biz_b.id, barcode=barcode, phone="+77017778899")
    db_session.add_all([card_a, card_b])
    await db_session.commit()

    resp = await client.post("/me/cards/bind", json={"barcode": barcode}, headers=headers)
    assert resp.status_code == 409
    err = resp.json()["error"]
    assert err["code"] == "BUSINESS_SELECTION_REQUIRED"
    assert "businesses" in err
    businesses = err["businesses"]
    assert len(businesses) == 2
    biz_ids = {b["id"] for b in businesses}
    assert str(biz_a.id) in biz_ids
    assert str(biz_b.id) in biz_ids
    # Verify no PII
    for b in businesses:
        assert "phone" not in b
        assert "balance" not in b
        assert "full_name" not in b


@pytest.mark.asyncio
async def test_bind_card_business_selection_required_no_matching_prefix(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Same barcode across 2 businesses without matching prefixes requires selection."""
    _, token = await create_test_customer(db_session, phone="+77017778899")
    headers = {"Authorization": f"Bearer {token}"}

    barcode = "0123456789012"

    biz_a = Business(name="Market 1", barcode_prefixes=["888"], status="active")
    biz_b = Business(name="Market 2", barcode_prefixes=["999"], status="active")
    db_session.add_all([biz_a, biz_b])
    await db_session.flush()

    card_a = Card(business_id=biz_a.id, barcode=barcode, phone="+77017778899")
    card_b = Card(business_id=biz_b.id, barcode=barcode, phone="+77017778899")
    db_session.add_all([card_a, card_b])
    await db_session.commit()

    resp = await client.post("/me/cards/bind", json={"barcode": barcode}, headers=headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "BUSINESS_SELECTION_REQUIRED"

    # User repeats with selected business_id
    resp2 = await client.post(
        "/me/cards/bind",
        json={"barcode": barcode, "business_id": str(biz_b.id)},
        headers=headers,
    )
    assert resp2.status_code == 200
    assert resp2.json()["id"] == str(card_b.id)


@pytest.mark.asyncio
async def test_bind_card_phone_ownership_and_normalization(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test phone normalization matching: 8701... matches +7701..."""
    _, token = await create_test_customer(db_session, phone="+77013334455")
    headers = {"Authorization": f"Bearer {token}"}

    biz = Business(name="Supermarket", status="active")
    db_session.add(biz)
    await db_session.flush()

    # Card has phone formatted as "87013334455"
    card = Card(
        business_id=biz.id,
        barcode="0123456789012",
        phone="87013334455",
        balance=Decimal("300.0000"),
    )
    db_session.add(card)
    await db_session.commit()

    resp = await client.post(
        "/me/cards/bind",
        json={"barcode": "0123456789012"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == str(card.id)


@pytest.mark.asyncio
async def test_bind_card_phone_mismatch_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Card with different phone returns 409 CARD_BIND_NOT_ALLOWED without leak."""
    _, token = await create_test_customer(db_session, phone="+77011111111")
    headers = {"Authorization": f"Bearer {token}"}

    biz = Business(name="Supermarket", status="active")
    db_session.add(biz)
    await db_session.flush()

    card = Card(
        business_id=biz.id,
        barcode="0123456789012",
        phone="+77019999999",  # Different phone
        balance=Decimal("500.0000"),
    )
    db_session.add(card)
    await db_session.commit()

    resp = await client.post(
        "/me/cards/bind",
        json={"barcode": "0123456789012"},
        headers=headers,
    )
    assert resp.status_code == 409
    err = resp.json()["error"]
    assert err["code"] == "CARD_BIND_NOT_ALLOWED"
    assert "+77019999999" not in str(err)
    assert "+77011111111" not in str(err)


@pytest.mark.asyncio
async def test_bind_card_phone_null_requires_activation(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Card with phone=NULL returns 409 CARD_ACTIVATION_REQUIRED."""
    _, token = await create_test_customer(db_session, phone="+77012223344")
    headers = {"Authorization": f"Bearer {token}"}

    biz = Business(name="Supermarket", status="active")
    db_session.add(biz)
    await db_session.flush()

    card = Card(
        business_id=biz.id,
        barcode="0123456789012",
        phone=None,
        balance=Decimal("500.0000"),
    )
    db_session.add(card)
    await db_session.commit()

    resp = await client.post(
        "/me/cards/bind",
        json={"barcode": "0123456789012"},
        headers=headers,
    )
    assert resp.status_code == 409
    err = resp.json()["error"]
    assert err["code"] == "CARD_ACTIVATION_REQUIRED"


@pytest.mark.asyncio
async def test_bind_card_malformed_phone_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Card with unparseable phone returns generic 409 CARD_BIND_NOT_ALLOWED."""
    _, token = await create_test_customer(db_session, phone="+77012223344")
    headers = {"Authorization": f"Bearer {token}"}

    biz = Business(name="Supermarket", status="active")
    db_session.add(biz)
    await db_session.flush()

    card = Card(
        business_id=biz.id,
        barcode="0123456789012",
        phone="invalid-phone-string",
        balance=Decimal("500.0000"),
    )
    db_session.add(card)
    await db_session.commit()

    resp = await client.post(
        "/me/cards/bind",
        json={"barcode": "0123456789012"},
        headers=headers,
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CARD_BIND_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_bind_card_existing_own_card_idempotent(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Binding an already bound visible card returns 200 OK without creating duplicates."""
    user, token = await create_test_customer(db_session, phone="+77014445566")
    headers = {"Authorization": f"Bearer {token}"}

    biz = Business(name="Supermarket", status="active")
    db_session.add(biz)
    await db_session.flush()

    card = Card(
        business_id=biz.id,
        barcode="0123456789012",
        phone="+77014445566",
        balance=Decimal("500.0000"),
    )
    db_session.add(card)
    await db_session.flush()

    initial_bound_at = utcnow()
    user_card = UserCard(
        user_id=user.id,
        card_id=card.id,
        bound_at=initial_bound_at,
        bind_method="phone_auto",
        hidden_at=None,
    )
    db_session.add(user_card)
    await db_session.commit()

    resp = await client.post(
        "/me/cards/bind",
        json={"barcode": "0123456789012"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(card.id)
    assert data["bind_method"] == "phone_auto"

    # Verify only 1 UserCard exists
    res = await db_session.execute(select(UserCard).where(UserCard.card_id == card.id))
    bindings = res.scalars().all()
    assert len(bindings) == 1


@pytest.mark.asyncio
async def test_bind_card_explicit_unhide_own_hidden_card(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Explicitly binding a previously soft-hidden own card unhides it."""
    user, token = await create_test_customer(db_session, phone="+77014445566")
    headers = {"Authorization": f"Bearer {token}"}

    biz = Business(name="Supermarket", status="active")
    db_session.add(biz)
    await db_session.flush()

    card = Card(
        business_id=biz.id,
        barcode="0123456789012",
        phone="+77014445566",
        balance=Decimal("500.0000"),
    )
    db_session.add(card)
    await db_session.flush()

    initial_bound_at = utcnow()
    user_card = UserCard(
        user_id=user.id,
        card_id=card.id,
        bound_at=initial_bound_at,
        bind_method="phone_auto",
        hidden_at=utcnow(),
    )
    db_session.add(user_card)
    await db_session.commit()

    resp = await client.post(
        "/me/cards/bind",
        json={"barcode": "0123456789012"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(card.id)
    assert data["bind_method"] == "phone_auto"

    # Verify hidden_at is now None
    updated_uc = (
        await db_session.execute(select(UserCard).where(UserCard.card_id == card.id))
    ).scalar_one()
    assert updated_uc.hidden_at is None
    assert updated_uc.bind_method == "phone_auto"


@pytest.mark.asyncio
async def test_bind_card_foreign_owner_cannot_be_stolen(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Card owned by User A cannot be bound by User B (even if phone was somehow matched)."""
    user_a, _ = await create_test_customer(db_session, phone="+77011110000")
    _, token_b = await create_test_customer(db_session, phone="+77012220000")
    headers_b = {"Authorization": f"Bearer {token_b}"}

    biz = Business(name="Supermarket", status="active")
    db_session.add(biz)
    await db_session.flush()

    card = Card(
        business_id=biz.id,
        barcode="0123456789012",
        phone="+77011110000",
        balance=Decimal("500.0000"),
    )
    db_session.add(card)
    await db_session.flush()

    user_card_a = UserCard(
        user_id=user_a.id,
        card_id=card.id,
        bind_method="manual_barcode",
        hidden_at=None,
    )
    db_session.add(user_card_a)
    await db_session.commit()

    # User B attempts to bind
    resp = await client.post(
        "/me/cards/bind",
        json={"barcode": "0123456789012"},
        headers=headers_b,
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CARD_BIND_NOT_ALLOWED"

    # Verify User A remains sole owner
    owner = (
        await db_session.execute(select(UserCard.user_id).where(UserCard.card_id == card.id))
    ).scalar_one()
    assert owner == user_a.id


@pytest.mark.asyncio
async def test_bind_card_foreign_hidden_owner_cannot_be_stolen(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Card owned by User A (even if soft-hidden) cannot be stolen by User B."""
    user_a, _ = await create_test_customer(db_session, phone="+77013330000")
    _, token_b = await create_test_customer(db_session, phone="+77014440000")
    headers_b = {"Authorization": f"Bearer {token_b}"}

    biz = Business(name="Supermarket", status="active")
    db_session.add(biz)
    await db_session.flush()

    card = Card(
        business_id=biz.id,
        barcode="0123456789012",
        phone="+77013330000",
        balance=Decimal("500.0000"),
    )
    db_session.add(card)
    await db_session.flush()

    user_card_a = UserCard(
        user_id=user_a.id,
        card_id=card.id,
        bind_method="manual_barcode",
        hidden_at=utcnow(),
    )
    db_session.add(user_card_a)
    await db_session.commit()

    resp = await client.post(
        "/me/cards/bind",
        json={"barcode": "0123456789012"},
        headers=headers_b,
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CARD_BIND_NOT_ALLOWED"

    # Verify User A remains sole owner
    uc = (
        await db_session.execute(select(UserCard).where(UserCard.card_id == card.id))
    ).scalar_one()
    assert uc.user_id == user_a.id
    assert uc.hidden_at is not None


@pytest.mark.asyncio
async def test_bind_card_blocked_card_succeeds(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Blocked card with matching phone binds successfully with is_blocked=True."""
    _, token = await create_test_customer(db_session, phone="+77019998877")
    headers = {"Authorization": f"Bearer {token}"}

    biz = Business(name="Supermarket", status="active")
    db_session.add(biz)
    await db_session.flush()

    initial_updated_at = utcnow()
    card = Card(
        business_id=biz.id,
        barcode="0123456789012",
        phone="+77019998877",
        balance=Decimal("750.0000"),
        is_blocked=True,
        updated_at=initial_updated_at,
    )
    db_session.add(card)
    await db_session.commit()

    resp = await client.post(
        "/me/cards/bind",
        json={"barcode": "0123456789012"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_blocked"] is True
    assert data["balance"] == "750.0000"

    # Verify Card entity untouched
    c = await db_session.get(Card, card.id)
    assert c is not None
    assert c.is_blocked is True
    assert c.balance == Decimal("750.0000")
    assert c.updated_at == initial_updated_at


@pytest.mark.asyncio
async def test_bind_card_mirror_attributes_strictly_read_only(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Manual bind strictly read-only: balance, phone, full_name, updated_at are unchanged."""
    _, token = await create_test_customer(db_session, phone="+77017770011")
    headers = {"Authorization": f"Bearer {token}"}

    biz = Business(name="Read Only Test Biz", status="active")
    db_session.add(biz)
    await db_session.flush()

    ts = utcnow()
    card = Card(
        business_id=biz.id,
        barcode="0123456789012",
        phone="+77017770011",
        full_name="Ivan Ivanov",
        balance=Decimal("1234.5600"),
        is_blocked=False,
        updated_at=ts,
    )
    db_session.add(card)
    await db_session.commit()

    resp = await client.post(
        "/me/cards/bind",
        json={"barcode": "0123456789012"},
        headers=headers,
    )
    assert resp.status_code == 200

    # Verify mirror card in DB
    refreshed_card = await db_session.get(Card, card.id)
    assert refreshed_card is not None
    assert refreshed_card.balance == Decimal("1234.5600")
    assert refreshed_card.phone == "+77017770011"
    assert refreshed_card.full_name == "Ivan Ivanov"
    assert refreshed_card.is_blocked is False
    assert refreshed_card.updated_at == ts
