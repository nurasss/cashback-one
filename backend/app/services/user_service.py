import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.phone import normalize_phone
from app.models.entities import User


async def get_or_create_user_by_phone(
    session: AsyncSession,
    raw_phone: str,
    language: str = "ru",
) -> User:
    """Resolve or create customer identity by normalized phone atomically.

    Guarantees 'one normalized phone -> one User' invariant under concurrent requests
    using database-level ON CONFLICT DO NOTHING, preserving existing user profile
    fields (including language preferences).
    """
    normalized_phone = normalize_phone(raw_phone)
    bind = session.get_bind()

    user_uuid = uuid.uuid4()
    if bind.dialect.name == "postgresql":
        stmt = (
            pg_insert(User)
            .values(id=user_uuid, phone=normalized_phone, language=language)
            .on_conflict_do_nothing(index_elements=["phone"])
            .returning(User.id)
        )
    else:
        stmt = (
            sqlite_insert(User)
            .values(id=user_uuid, phone=normalized_phone, language=language)
            .on_conflict_do_nothing(index_elements=["phone"])
            .returning(User.id)
        )

    result = await session.execute(stmt)
    resolved_id: uuid.UUID | None = result.scalar_one_or_none()
    if resolved_id is None:
        select_stmt = select(User.id).where(User.phone == normalized_phone)
        resolved_id = (await session.execute(select_stmt)).scalar_one()

    return await session.get_one(User, resolved_id)



def ensure_user_active(user: User) -> None:
    """Reject token issuance for soft-deleted customer accounts."""
    if user.deleted_at is not None:
        raise AppError(
            code="ACCOUNT_DEACTIVATED",
            message="Customer account is deactivated",
            status_code=403,
        )
