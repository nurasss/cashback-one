import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cli.create_admin import provision_admin
from app.models.admin import AdminUser
from app.models.entities import Business
from app.services.admin_security import verify_admin_password

TEST_PASSWORD = "fixture-only-superadmin-password"

@pytest.mark.asyncio
async def test_interactive_provision_creates_only_argon2_hash(db_session: AsyncSession) -> None:
    identity = Business(name="Fixture business", status="active")
    db_session.add(identity)
    await db_session.flush()
    await provision_admin(db_session, "Root.Operator", TEST_PASSWORD, "superadmin", None)
    account = await db_session.scalar(select(AdminUser).where(AdminUser.login == "root.operator"))
    assert account is not None
    assert account.business_id is None
    assert account.password_hash.startswith("$argon2id$")
    assert account.password_hash != TEST_PASSWORD
    assert verify_admin_password(account.password_hash, TEST_PASSWORD)
    assert await db_session.scalar(select(AdminUser).where(AdminUser.login == "admin")) is None


def test_cli_prompts_without_echoing_a_manager_password(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from uuid import uuid4

    import app.cli.create_admin as cli

    business_id = uuid4()
    answers = iter([" Manager.Test ", "business_manager", str(business_id)])
    passwords = iter(["fixture-only-manager-password", "fixture-only-manager-password"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    monkeypatch.setattr(cli, "getpass", lambda _prompt: next(passwords))
    login, password, role, resolved_business = cli._read_admin_identity()
    assert (login, role, resolved_business) == ("manager.test", "business_manager", business_id)
    assert password == "fixture-only-manager-password"
    assert capsys.readouterr().out == ""
