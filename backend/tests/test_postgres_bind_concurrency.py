import asyncio
import os
import uuid
from collections.abc import AsyncGenerator
from datetime import timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import create_access_token, hash_refresh_token
from app.core.time import utcnow
from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models.entities import AuthSession, Business, Card, User, UserCard


@pytest.fixture
async def pg_engine():  # type: ignore[no-untyped-def]
    pg_url = os.environ.get("POSTGRES_TEST_URL")
    if not pg_url:
        pytest.skip("POSTGRES_TEST_URL is not configured")

    try:
        engine = create_async_engine(pg_url, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except (SQLAlchemyError, OSError) as exc:
        pytest.skip(f"PostgreSQL connection skipped: {exc}")

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def pg_session_maker(pg_engine):  # type: ignore[no-untyped-def]
    return async_sessionmaker(pg_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.mark.asyncio
async def test_pg_bind_01_concurrent_same_user_manual_bind(
    pg_session_maker,  # type: ignore[no-untyped-def]
) -> None:
    """PG-BIND-01: Concurrent POST /me/cards/bind for the same user and card.

    Ensures:
    - 5 concurrent requests with asyncio.Barrier(5)
    - Exactly 1 UserCard created
    - 0 IntegrityError, 0 HTTP 500
    - All responses return 200 OK with correct card representation
    """
    phone = "+77015551122"
    barcode = "0123456789012"

    async with pg_session_maker() as s:
        biz = Business(name="PG Biz Alpha", barcode_prefixes=["012"], status="active")
        s.add(biz)
        await s.flush()

        card = Card(
            business_id=biz.id,
            barcode=barcode,
            phone=phone,
            balance=Decimal("350.0000"),
        )
        s.add(card)

        user = User(phone=phone, language="ru")
        s.add(user)
        await s.flush()

        auth_session = AuthSession(
            user_id=user.id,
            device_id="pg-device-1",
            refresh_token_hash=hash_refresh_token(f"rfr_{uuid.uuid4()}"),
            expires_at=utcnow() + timedelta(days=30),
        )
        s.add(auth_session)
        await s.commit()

        token = create_access_token(user_id=user.id, session_id=auth_session.id)
        card_id = card.id

    async def get_test_session() -> AsyncGenerator[AsyncSession, None]:
        async with pg_session_maker() as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    try:
        barrier = asyncio.Barrier(5)

        async def worker(ac: AsyncClient) -> tuple[int, dict]:  # type: ignore[type-arg]
            await barrier.wait()
            resp = await ac.post(
                "/me/cards/bind",
                json={"barcode": barcode},
                headers={"Authorization": f"Bearer {token}"},
            )
            return resp.status_code, resp.json()

        async with AsyncClient(
            transport=ASGITransport(app=app),  # type: ignore[arg-type]
            base_url="http://test",
        ) as ac:
            results = await asyncio.gather(*(worker(ac) for _ in range(5)))

        status_codes = [r[0] for r in results]
        assert status_codes == [200, 200, 200, 200, 200]
        for _, body in results:
            assert body["id"] == str(card_id)
            assert body["barcode"] == barcode
            assert body["bind_method"] == "manual_barcode"

        # Verify DB state
        async with pg_session_maker() as s:
            rows = (
                await s.execute(select(UserCard).where(UserCard.card_id == card_id))
            ).scalars().all()
            assert len(rows) == 1
            assert rows[0].user_id == user.id
            assert rows[0].bind_method == "manual_barcode"
            assert rows[0].hidden_at is None
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_pg_bind_02_foreign_existing_owner_cannot_be_stolen(
    pg_session_maker,  # type: ignore[no-untyped-def]
) -> None:
    """PG-BIND-02: User B cannot bind or steal card already owned by User A."""
    phone_a = "+77011119999"
    phone_b = "+77012229999"
    barcode = "0123456789012"

    async with pg_session_maker() as s:
        biz = Business(name="PG Biz Beta", status="active")
        s.add(biz)
        await s.flush()

        card = Card(
            business_id=biz.id,
            barcode=barcode,
            phone=phone_a,
            balance=Decimal("600.0000"),
        )
        s.add(card)

        user_a = User(phone=phone_a, language="ru")
        user_b = User(phone=phone_b, language="ru")
        s.add_all([user_a, user_b])
        await s.flush()

        # User A owns card
        uc_a = UserCard(
            user_id=user_a.id,
            card_id=card.id,
            bind_method="manual_barcode",
            hidden_at=None,
        )
        s.add(uc_a)

        sess_b = AuthSession(
            user_id=user_b.id,
            device_id="pg-device-b",
            refresh_token_hash=hash_refresh_token(f"rfr_{uuid.uuid4()}"),
            expires_at=utcnow() + timedelta(days=30),
        )
        s.add(sess_b)
        await s.commit()

        token_b = create_access_token(user_id=user_b.id, session_id=sess_b.id)
        card_id = card.id
        user_a_id = user_a.id

    async def get_test_session() -> AsyncGenerator[AsyncSession, None]:
        async with pg_session_maker() as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),  # type: ignore[arg-type]
            base_url="http://test",
        ) as ac:
            resp = await ac.post(
                "/me/cards/bind",
                json={"barcode": barcode},
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert resp.status_code == 409
            assert resp.json()["error"]["code"] == "CARD_BIND_NOT_ALLOWED"

        # Ownership remains strictly User A
        async with pg_session_maker() as s:
            owner = (
                await s.execute(select(UserCard.user_id).where(UserCard.card_id == card_id))
            ).scalar_one()
            assert owner == user_a_id
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_pg_bind_03_concurrent_manual_unhide(
    pg_session_maker,  # type: ignore[no-untyped-def]
) -> None:
    """PG-BIND-03: Concurrent manual unhide of soft-hidden card by the owner.

    Ensures:
    - 5 concurrent requests with barrier
    - 1 UserCard remains in DB
    - hidden_at becomes NULL
    - original bound_at and bind_method preserved
    - 0 x 500
    """
    phone = "+77017773344"
    barcode = "0123456789012"

    async with pg_session_maker() as s:
        biz = Business(name="PG Biz Gamma", status="active")
        s.add(biz)
        await s.flush()

        card = Card(
            business_id=biz.id,
            barcode=barcode,
            phone=phone,
            balance=Decimal("450.0000"),
        )
        s.add(card)

        user = User(phone=phone, language="ru")
        s.add(user)
        await s.flush()

        initial_bound_at = utcnow() - timedelta(days=10)
        uc = UserCard(
            user_id=user.id,
            card_id=card.id,
            bound_at=initial_bound_at,
            bind_method="phone_auto",
            hidden_at=utcnow() - timedelta(days=2),
        )
        s.add(uc)

        sess = AuthSession(
            user_id=user.id,
            device_id="pg-device-unhide",
            refresh_token_hash=hash_refresh_token(f"rfr_{uuid.uuid4()}"),
            expires_at=utcnow() + timedelta(days=30),
        )
        s.add(sess)
        await s.commit()

        token = create_access_token(user_id=user.id, session_id=sess.id)
        card_id = card.id

    async def get_test_session() -> AsyncGenerator[AsyncSession, None]:
        async with pg_session_maker() as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    try:
        barrier = asyncio.Barrier(5)

        async def worker(ac: AsyncClient) -> int:
            await barrier.wait()
            resp = await ac.post(
                "/me/cards/bind",
                json={"barcode": barcode},
                headers={"Authorization": f"Bearer {token}"},
            )
            return resp.status_code

        async with AsyncClient(
            transport=ASGITransport(app=app),  # type: ignore[arg-type]
            base_url="http://test",
        ) as ac:
            status_codes = await asyncio.gather(*(worker(ac) for _ in range(5)))

        assert status_codes == [200, 200, 200, 200, 200]

        async with pg_session_maker() as s:
            updated_uc = (
                await s.execute(select(UserCard).where(UserCard.card_id == card_id))
            ).scalar_one()
            assert updated_uc.hidden_at is None
            assert updated_uc.bind_method == "phone_auto"
            assert updated_uc.bound_at == initial_bound_at
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_pg_bind_04_same_barcode_two_businesses_tenant_safe(
    pg_session_maker,  # type: ignore[no-untyped-def]
) -> None:
    """PG-BIND-04: Same barcode across 2 businesses remains tenant-isolated."""
    phone = "+77018889900"
    barcode = "0123456789012"

    async with pg_session_maker() as s:
        biz_a = Business(name="Biz A", barcode_prefixes=["012"], status="active")
        biz_b = Business(name="Biz B", barcode_prefixes=["777"], status="active")
        s.add_all([biz_a, biz_b])
        await s.flush()

        card_a = Card(business_id=biz_a.id, barcode=barcode, phone=phone, balance=Decimal("100.0000"))
        card_b = Card(business_id=biz_b.id, barcode=barcode, phone=phone, balance=Decimal("200.0000"))
        s.add_all([card_a, card_b])

        user = User(phone=phone, language="ru")
        s.add(user)
        await s.flush()

        sess = AuthSession(
            user_id=user.id,
            device_id="pg-device-tenant",
            refresh_token_hash=hash_refresh_token(f"rfr_{uuid.uuid4()}"),
            expires_at=utcnow() + timedelta(days=30),
        )
        s.add(sess)
        await s.commit()

        token = create_access_token(user_id=user.id, session_id=sess.id)
        biz_a_id = biz_a.id
        biz_b_id = biz_b.id
        card_a_id = card_a.id
        card_b_id = card_b.id

    async def get_test_session() -> AsyncGenerator[AsyncSession, None]:
        async with pg_session_maker() as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),  # type: ignore[arg-type]
            base_url="http://test",
        ) as ac:
            # 1. Without business_id: prefix resolves Biz A
            resp_a = await ac.post(
                "/me/cards/bind",
                json={"barcode": barcode},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp_a.status_code == 200
            assert resp_a.json()["id"] == str(card_a_id)
            assert resp_a.json()["business"]["id"] == str(biz_a_id)

            # 2. With explicit business_id for Biz B
            resp_b = await ac.post(
                "/me/cards/bind",
                json={"barcode": barcode, "business_id": str(biz_b_id)},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp_b.status_code == 200
            assert resp_b.json()["id"] == str(card_b_id)
            assert resp_b.json()["business"]["id"] == str(biz_b_id)

        # In DB: exactly 2 distinct user_cards, each linked to their respective card
        async with pg_session_maker() as s:
            user_cards = (
                await s.execute(select(UserCard).where(UserCard.user_id == user.id))
            ).scalars().all()
            assert len(user_cards) == 2
            card_ids = {uc.card_id for uc in user_cards}
            assert card_ids == {card_a_id, card_b_id}
    finally:
        app.dependency_overrides.pop(get_session, None)
