"""Tests for customer profile avatar upload, delete, storage, security, and migration."""
import io

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.main import app
from app.services.media_storage import (
    SAFE_MEDIA_PATH_REGEX,
    DisabledMediaStorage,
    InMemoryMediaStorage,
    get_media_storage,
)
from app.services.rate_limiter import _test_limiter
from tests.test_customer_app import customer


@pytest.fixture(autouse=True)
def reset_limiter() -> None:
    _test_limiter.reset()


@pytest.fixture
def fake_storage() -> InMemoryMediaStorage:
    storage = InMemoryMediaStorage()
    app.dependency_overrides[get_media_storage] = lambda: storage
    yield storage
    app.dependency_overrides.pop(get_media_storage, None)


def _make_jpeg(width: int = 600, height: int = 400, exif_data: bool = False) -> bytes:
    im = Image.new("RGB", (width, height), color=(200, 100, 50))
    bio = io.BytesIO()
    if exif_data:
        exif = im.getexif()
        exif[0x0112] = 6  # Orientation
        exif[0x010E] = "Sample GPS & camera metadata test"
        im.save(bio, format="JPEG", exif=exif)
    else:
        im.save(bio, format="JPEG")
    return bio.getvalue()


def _make_rgba_png(width: int = 300, height: int = 300) -> bytes:
    im = Image.new("RGBA", (width, height), color=(0, 200, 100, 128))
    bio = io.BytesIO()
    im.save(bio, format="PNG")
    return bio.getvalue()


@pytest.mark.asyncio
async def test_avatar_upload_success_and_format(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_storage: InMemoryMediaStorage,
) -> None:
    """Upload creates 512x512 WebP in avatars/ path and updates profile."""
    user, headers = await customer(db_session, "+77019990001")
    jpeg_data = _make_jpeg(800, 600)

    res = await client.post(
        "/me/avatar",
        headers=headers,
        files={"file": ("photo.jpg", jpeg_data, "image/jpeg")},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["avatar_url"] is not None
    assert body["avatar_url"].startswith(f"{settings.media_public_base_url}/avatars/")
    assert body["avatar_url"].endswith(".webp")

    # Check relative path matches SAFE_MEDIA_PATH_REGEX
    rel_path = body["avatar_url"].replace(f"{settings.media_public_base_url}/", "")
    assert SAFE_MEDIA_PATH_REGEX.match(rel_path)

    # Check stored image properties
    stored_bytes = fake_storage.files[rel_path]
    stored_im = Image.open(io.BytesIO(stored_bytes))
    assert stored_im.format == "WEBP"
    assert stored_im.size == (512, 512)

    # Verify database was updated
    await db_session.refresh(user)
    assert user.avatar_url == body["avatar_url"]


@pytest.mark.asyncio
async def test_avatar_upload_exif_gps_stripped(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_storage: InMemoryMediaStorage,
) -> None:
    """EXIF metadata with GPS coordinates is completely stripped from the output WebP."""
    _, headers = await customer(db_session, "+77019990002")
    jpeg_with_exif = _make_jpeg(400, 400, exif_data=True)

    res = await client.post(
        "/me/avatar",
        headers=headers,
        files={"file": ("photo.jpg", jpeg_with_exif, "image/jpeg")},
    )
    assert res.status_code == 200
    avatar_url = res.json()["avatar_url"]
    rel_path = avatar_url.replace(f"{settings.media_public_base_url}/", "")

    stored_bytes = fake_storage.files[rel_path]
    stored_im = Image.open(io.BytesIO(stored_bytes))
    assert "exif" not in stored_im.info
    exif_tags = stored_im.getexif()
    assert len(exif_tags) == 0


@pytest.mark.asyncio
async def test_avatar_upload_rgba_png_and_invalid_files(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_storage: InMemoryMediaStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RGBA PNG succeeds; corrupt file and file exceeding size limit are rejected."""
    _, headers = await customer(db_session, "+77019990003")

    # 1. RGBA PNG succeeds
    png_data = _make_rgba_png(400, 400)
    res_png = await client.post(
        "/me/avatar",
        headers=headers,
        files={"file": ("avatar.png", png_data, "image/png")},
    )
    assert res_png.status_code == 200
    assert res_png.json()["avatar_url"].endswith(".webp")

    # 2. Corrupt non-image rejected with 415
    res_corrupt = await client.post(
        "/me/avatar",
        headers=headers,
        files={"file": ("document.txt", b"plain text content not image", "text/plain")},
    )
    assert res_corrupt.status_code == 415
    assert res_corrupt.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"

    # 3. File exceeding limit rejected with 413 FILE_TOO_LARGE
    monkeypatch.setattr(settings, "avatar_max_upload_bytes", 500)
    res_large = await client.post(
        "/me/avatar",
        headers=headers,
        files={"file": ("large.jpg", b"X" * 600, "image/jpeg")},
    )
    assert res_large.status_code == 413
    assert res_large.json()["error"]["code"] == "FILE_TOO_LARGE"


@pytest.mark.asyncio
async def test_avatar_replacement_deletes_old_file_and_tolerates_cleanup_error(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_storage: InMemoryMediaStorage,
) -> None:
    """Replacing avatar deletes old file; error during old file deletion does not fail response."""
    _user, headers = await customer(db_session, "+77019990004")

    # Upload avatar 1
    res1 = await client.post(
        "/me/avatar",
        headers=headers,
        files={"file": ("a1.jpg", _make_jpeg(200, 200), "image/jpeg")},
    )
    assert res1.status_code == 200
    url1 = res1.json()["avatar_url"]
    path1 = url1.replace(f"{settings.media_public_base_url}/", "")
    assert path1 in fake_storage.files

    # Upload avatar 2 -> deletes avatar 1
    res2 = await client.post(
        "/me/avatar",
        headers=headers,
        files={"file": ("a2.jpg", _make_jpeg(300, 300), "image/jpeg")},
    )
    assert res2.status_code == 200
    url2 = res2.json()["avatar_url"]
    path2 = url2.replace(f"{settings.media_public_base_url}/", "")
    assert path2 in fake_storage.files
    assert path1 not in fake_storage.files

    # Simulate storage delete failure: uploading avatar 3 still succeeds
    fake_storage.fail_delete = True
    res3 = await client.post(
        "/me/avatar",
        headers=headers,
        files={"file": ("a3.jpg", _make_jpeg(400, 400), "image/jpeg")},
    )
    assert res3.status_code == 200
    url3 = res3.json()["avatar_url"]
    path3 = url3.replace(f"{settings.media_public_base_url}/", "")
    assert path3 in fake_storage.files


@pytest.mark.asyncio
async def test_avatar_storage_failure_leaves_db_unchanged(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_storage: InMemoryMediaStorage,
) -> None:
    """If storage.put fails, DB avatar_url is not updated."""
    user, headers = await customer(db_session, "+77019990005")
    initial_avatar = user.avatar_url

    fake_storage.fail_put = True
    res = await client.post(
        "/me/avatar",
        headers=headers,
        files={"file": ("test.jpg", _make_jpeg(200, 200), "image/jpeg")},
    )
    assert res.status_code == 502
    await db_session.refresh(user)
    assert user.avatar_url == initial_avatar


@pytest.mark.asyncio
async def test_avatar_delete_endpoint(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_storage: InMemoryMediaStorage,
) -> None:
    """DELETE /me/avatar removes file and clears avatar_url; repeating is idempotent."""
    user, headers = await customer(db_session, "+77019990006")

    # Upload avatar
    res_up = await client.post(
        "/me/avatar",
        headers=headers,
        files={"file": ("av.jpg", _make_jpeg(200, 200), "image/jpeg")},
    )
    assert res_up.status_code == 200
    url = res_up.json()["avatar_url"]
    path = url.replace(f"{settings.media_public_base_url}/", "")
    assert path in fake_storage.files

    # Delete avatar
    res_del1 = await client.delete("/me/avatar", headers=headers)
    assert res_del1.status_code == 200
    assert res_del1.json()["avatar_url"] is None
    assert path not in fake_storage.files

    await db_session.refresh(user)
    assert user.avatar_url is None

    # Delete again is idempotent
    res_del2 = await client.delete("/me/avatar", headers=headers)
    assert res_del2.status_code == 200
    assert res_del2.json()["avatar_url"] is None


@pytest.mark.asyncio
async def test_avatar_auth_and_rate_limit(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_storage: InMemoryMediaStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anonymous request gets 401; exceeding rate limit gives 429."""
    # 1. No token -> 401
    res_anon = await client.post(
        "/me/avatar",
        files={"file": ("av.jpg", _make_jpeg(200, 200), "image/jpeg")},
    )
    assert res_anon.status_code == 401

    # 2. Rate limit
    monkeypatch.setattr(settings, "avatar_upload_user_limit", 2)
    monkeypatch.setattr(settings, "avatar_upload_window_seconds", 3600)
    _, headers = await customer(db_session, "+77019990007")

    res1 = await client.post("/me/avatar", headers=headers, files={"file": ("a.jpg", _make_jpeg(100, 100), "image/jpeg")})
    assert res1.status_code == 200
    res2 = await client.post("/me/avatar", headers=headers, files={"file": ("b.jpg", _make_jpeg(100, 100), "image/jpeg")})
    assert res2.status_code == 200

    # 3rd request exceeds limit
    res3 = await client.post("/me/avatar", headers=headers, files={"file": ("c.jpg", _make_jpeg(100, 100), "image/jpeg")})
    assert res3.status_code == 429
    assert res3.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_avatar_patch_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """PATCH /me/profile cannot set avatar_url directly (extra=forbid)."""
    _, headers = await customer(db_session, "+77019990008")
    res = await client.patch(
        "/me/profile",
        headers=headers,
        json={"avatar_url": "https://attacker.com/evil.jpg"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_avatar_shared_reference_protection(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_storage: InMemoryMediaStorage,
) -> None:
    """If another user references the same avatar file, deleting one user's avatar does not delete file."""
    _user1, headers1 = await customer(db_session, "+77019990009")
    user2, _ = await customer(db_session, "+77019990010")

    res = await client.post(
        "/me/avatar",
        headers=headers1,
        files={"file": ("shared.jpg", _make_jpeg(200, 200), "image/jpeg")},
    )
    assert res.status_code == 200
    url = res.json()["avatar_url"]
    path = url.replace(f"{settings.media_public_base_url}/", "")

    # User 2 points to the same avatar URL
    user2.avatar_url = url
    await db_session.commit()

    # User 1 deletes avatar
    res_del = await client.delete("/me/avatar", headers=headers1)
    assert res_del.status_code == 200
    assert res_del.json()["avatar_url"] is None

    # File must still exist in storage because user2 references it
    assert path in fake_storage.files


@pytest.mark.asyncio
async def test_avatar_disabled_storage(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """When media storage is disabled, upload returns 503 MEDIA_STORAGE_NOT_CONFIGURED."""
    app.dependency_overrides[get_media_storage] = lambda: DisabledMediaStorage()
    try:
        _, headers = await customer(db_session, "+77019990011")
        res = await client.post(
            "/me/avatar",
            headers=headers,
            files={"file": ("av.jpg", _make_jpeg(200, 200), "image/jpeg")},
        )
        assert res.status_code == 503
        assert res.json()["error"]["code"] == "MEDIA_STORAGE_NOT_CONFIGURED"
    finally:
        app.dependency_overrides.pop(get_media_storage, None)


def test_avatar_migration_upgrade_and_downgrade() -> None:
    """Test 0011_customer_avatar migration upgrade and downgrade scripts."""
    import importlib
    migration = importlib.import_module("migrations.versions.0011_customer_avatar")

    # In-memory SQLite engine
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE users (id TEXT PRIMARY KEY, phone TEXT)"))
        conn.commit()

        # Run upgrade with alembic MigrationContext
        ctx = MigrationContext.configure(conn)
        op = Operations(ctx)
        migration.op = op
        migration.upgrade()
        conn.commit()

        # Verify avatar_url column exists
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(users)")).fetchall()]
        assert "avatar_url" in cols

        # Run downgrade
        migration.downgrade()
        conn.commit()

        # Verify avatar_url column was dropped
        cols_after = [row[1] for row in conn.execute(text("PRAGMA table_info(users)")).fetchall()]
        assert "avatar_url" not in cols_after
