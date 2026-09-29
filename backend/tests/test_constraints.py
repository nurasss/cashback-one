import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.models.entities import (
    Agent,
    AuditLog,
    Business,
    Card,
    Consent,
    Device,
    LoginChallenge,
    OtpCode,
    Transaction,
    User,
    UserCard,
)


@pytest.mark.asyncio
async def test_multi_tenant_cards_unique_constraint(db_session: AsyncSession) -> None:
    """Cards in different businesses can share barcode, but same business cannot duplicate."""
    business_a = Business(name="Market A")
    business_b = Business(name="Market B")
    db_session.add_all([business_a, business_b])
    await db_session.commit()

    shared_barcode = "1234567890123"

    # Business A card with shared_barcode
    card_a = Card(
        business_id=business_a.id,
        barcode=shared_barcode,
        balance=Decimal("1500.5000"),
    )
    # Business B card with shared_barcode
    card_b = Card(
        business_id=business_b.id,
        barcode=shared_barcode,
        balance=Decimal("300.0000"),
    )
    db_session.add_all([card_a, card_b])
    await db_session.commit()

    # Both must exist
    cards = (await db_session.scalars(select(Card).where(Card.barcode == shared_barcode))).all()
    assert len(cards) == 2

    # Attempting duplicate barcode in Business A must fail
    duplicate_card_a = Card(
        business_id=business_a.id,
        barcode=shared_barcode,
        balance=Decimal("0.0000"),
    )
    db_session.add(duplicate_card_a)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_transaction_unique_constraint(db_session: AsyncSession) -> None:
    """A card cannot have duplicate external_id transactions."""
    biz = Business(name="Test Biz")
    db_session.add(biz)
    await db_session.commit()

    card_1 = Card(business_id=biz.id, barcode="1111111111111")
    card_2 = Card(business_id=biz.id, barcode="2222222222222")
    db_session.add_all([card_1, card_2])
    await db_session.commit()

    tx_1 = Transaction(
        card_id=card_1.id,
        external_id="REC-001",
        type="accrual",
        amount=Decimal("50.0000"),
        balance_after=Decimal("50.0000"),
        occurred_at=utcnow(),
    )
    db_session.add(tx_1)
    await db_session.commit()

    # Same external_id for card_2 must succeed
    tx_2 = Transaction(
        card_id=card_2.id,
        external_id="REC-001",
        type="accrual",
        amount=Decimal("100.0000"),
        balance_after=Decimal("100.0000"),
        occurred_at=utcnow(),
    )
    db_session.add(tx_2)
    await db_session.commit()

    # Duplicate external_id for card_1 must raise IntegrityError
    tx_duplicate = Transaction(
        card_id=card_1.id,
        external_id="REC-001",
        type="accrual",
        amount=Decimal("20.0000"),
        balance_after=Decimal("70.0000"),
        occurred_at=utcnow(),
    )
    db_session.add(tx_duplicate)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_user_card_single_owner_constraint(db_session: AsyncSession) -> None:
    """A card cannot simultaneously belong to multiple users (DB-level constraint on card_id)."""
    biz = Business(name="Loyalty Retail")
    user_1 = User(phone="+77010000001")
    user_2 = User(phone="+77010000002")
    db_session.add_all([biz, user_1, user_2])
    await db_session.commit()

    card = Card(business_id=biz.id, barcode="3333333333333")
    db_session.add(card)
    await db_session.commit()

    # User 1 binds card
    user_card_1 = UserCard(user_id=user_1.id, card_id=card.id, bind_method="qr_scan")
    db_session.add(user_card_1)
    await db_session.commit()

    # User 2 attempts to bind the same card -> must violate UNIQUE(card_id)
    user_card_2 = UserCard(user_id=user_2.id, card_id=card.id, bind_method="qr_scan")
    db_session.add(user_card_2)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_foreign_key_constraints(db_session: AsyncSession) -> None:
    """Foreign key enforcement prevents orphan records and cascades deletions."""
    # Non-existent business_id for Card
    orphan_card = Card(business_id=uuid.uuid4(), barcode="9999999999999")
    db_session.add(orphan_card)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

    # Cascade deletion on Business -> Cards
    biz = Business(name="Deletable Biz")
    db_session.add(biz)
    await db_session.commit()

    card = Card(business_id=biz.id, barcode="4444444444444")
    agent = Agent(business_id=biz.id, key_hash="hash123")
    db_session.add_all([card, agent])
    await db_session.commit()

    await db_session.delete(biz)
    await db_session.commit()

    # Cards and Agents belonging to biz must be removed
    cards_remaining = (await db_session.scalars(select(Card).where(Card.id == card.id))).all()
    agents_remaining = (await db_session.scalars(select(Agent).where(Agent.id == agent.id))).all()
    assert len(cards_remaining) == 0
    assert len(agents_remaining) == 0


@pytest.mark.asyncio
async def test_money_and_balance_numeric_precision(db_session: AsyncSession) -> None:
    """Ensure decimal amounts and balances preserve high precision without float drift."""
    biz = Business(name="Precision Biz")
    db_session.add(biz)
    await db_session.commit()

    card = Card(
        business_id=biz.id,
        barcode="5555555555555",
        balance=Decimal("1234567.8912"),
    )
    db_session.add(card)
    await db_session.commit()

    fetched = await db_session.scalar(select(Card).where(Card.id == card.id))
    assert fetched is not None
    assert fetched.balance == Decimal("1234567.8912")
    assert isinstance(fetched.balance, Decimal)


@pytest.mark.asyncio
async def test_auxiliary_stage1_models_creation(db_session: AsyncSession) -> None:
    """Ensure login_challenges, otp_codes, consents, devices, and audit_log persist cleanly."""
    user = User(phone="+77009998877", language="kk")
    db_session.add(user)
    await db_session.commit()

    challenge = LoginChallenge(
        code_hash="sha256_dummy_code_hash",
        device_id="device_ios_001",
        status="pending",
        expires_at=utcnow(),
    )
    otp = OtpCode(
        phone="+77009998877",
        code_hash="sha256_dummy_otp_hash",
        expires_at=utcnow(),
        attempts=1,
    )
    consent = Consent(
        user_id=user.id,
        type="personal_data_processing",
        version="v1.0",
        given_at=utcnow(),
    )
    device = Device(
        user_id=user.id,
        push_token="fcm_token_sample",
        platform="ios",
    )
    audit = AuditLog(
        actor="superadmin",
        action="unbind_card",
        entity="user_cards",
        before_state={"user_id": str(user.id)},
        after_state=None,
    )

    db_session.add_all([challenge, otp, consent, device, audit])
    await db_session.commit()

    assert challenge.id is not None
    assert otp.id is not None
    assert consent.id is not None
    assert device.id is not None
    assert audit.id is not None
