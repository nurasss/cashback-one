"""Safely provision the first superadmin or a business-scoped manager."""
import asyncio
from getpass import getpass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_types import AdminRole
from app.models.admin import AdminUser
from app.models.entities import Business
from app.services.admin_security import hash_admin_password, normalize_admin_login


def _read_admin_identity() -> tuple[str, str, AdminRole, UUID | None]:
    while True:
        try:
            login = normalize_admin_login(input("Admin login: "))
            break
        except ValueError as err:
            print(str(err))

    while True:
        password = getpass("Password (minimum 12 characters): ")
        confirmation = getpass("Confirm password: ")
        try:
            if password != confirmation:
                raise ValueError("Passwords do not match")
            hash_admin_password(password)
            break
        except ValueError as err:
            print(str(err))

    while True:
        role_input = input("Role (superadmin/business_manager): ").strip().lower()
        if role_input in {"superadmin", "business_manager"}:
            role: AdminRole = role_input  # type: ignore[assignment]
            break
        print("Choose superadmin or business_manager.")

    business_id: UUID | None = None
    if role == "business_manager":
        while True:
            try:
                business_id = UUID(input("Business ID: ").strip())
                break
            except ValueError:
                print("Enter a valid existing Business ID.")
    return login, password, role, business_id


async def provision_admin(
    session: AsyncSession,
    login: str,
    password: str,
    role: AdminRole,
    business_id: UUID | None,
) -> None:
    normalized_login = normalize_admin_login(login)
    password_hash = hash_admin_password(password)
    if role not in {"superadmin", "business_manager"}:
        raise ValueError("Choose superadmin or business_manager")
    if role == "superadmin" and business_id is not None:
        raise ValueError("A superadmin cannot be assigned to a business")
    if role == "business_manager" and business_id is None:
        raise ValueError("A business manager requires an existing business")
    if business_id is not None:
        business = await session.scalar(select(Business.id).where(Business.id == business_id))
        if business is None:
            raise ValueError("The selected Business does not exist")

    session.add(
        AdminUser(
            login=normalized_login,
            password_hash=password_hash,
            role=role,
            business_id=business_id,
            is_active=True,
        )
    )
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise ValueError("That login is already provisioned") from None


async def _provision_interactively() -> None:
    from app.db.session import async_session_maker

    login, password, role, business_id = _read_admin_identity()
    async with async_session_maker() as session:
        await provision_admin(session, login, password, role, business_id)
    print("Admin account created.")


def main() -> None:
    asyncio.run(_provision_interactively())


if __name__ == "__main__":
    main()
