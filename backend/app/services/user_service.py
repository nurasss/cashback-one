import uuid

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.phone import normalize_phone
from app.models.entities import User


async def get_or_create_user_by_phone(
    session: AsyncSession,
    raw_phone: str,
    language: str = "ru",
) -> User:
    """Resolve or create customer identity by normalized phone atomically.

    Guarantees 'one normalized phone -> one User' invariant under concurrent requests
    using database-level ON CONFLICT DO UPDATE.
    """
    normalized_phone = normalize_phone(raw_phone)
    bind = session.get_bind()

    user_uuid = uuid.uuid4()
    if bind.dialect.name == "postgresql":
        stmt = (
            pg_insert(User)
            .values(id=user_uuid, phone=normalized_phone, language=language)
            .on_conflict_do_update(
                index_elements=["phone"],
                set_={"language": language},
            )
            .returning(User.id)
        )
    else:
        stmt = (
            sqlite_insert(User)
            .values(id=user_uuid, phone=normalized_phone, language=language)
            .on_conflict_do_update(
                index_elements=["phone"],
                set_={"language": language},
            )
            .returning(User.id)
        )

    resolved_id: uuid.UUID = (await session.execute(stmt)).scalar_one()
    return await session.get_one(User, resolved_id)
