"""Integration tests for app splash management, upload, storage scoping, public endpoint, and app-content."""
import io

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.main import app
from app.models.entities import AuditLog
from app.services.media_storage import (
    InMemoryMediaStorage,
    get_media_storage,
)
from tests.test_admin_mutations import (
    auth_headers,
    make_admin,
    make_business,
    mutation_client,  # noqa: F401
)
from tests.test_video_service import make_mp4


def _make_png(w: int = 100, h: int = 100) -> bytes:
    im = Image.new("RGBA", (w, h), color=(255, 100, 50, 255))
    bio = io.BytesIO()
    im.save(bio, format="PNG")
    return bio.getvalue()


@pytest.fixture
def fake_storage() -> InMemoryMediaStorage:
    storage = InMemoryMediaStorage()
    app.dependency_overrides[get_media_storage] = lambda: storage
    yield storage
    app.dependency_overrides.pop(get_media_storage, None)


@pytest.mark.asyncio
async def test_admin_upload_splash_image(
    db_session: AsyncSession,
    mutation_client: AsyncClient,  # noqa: F811
    fake_storage: InMemoryMediaStorage,
):
    admin = await make_admin(db_session, "superadmin", None, "super_splash")
    png_bytes = _make_png(200, 400)
    files = {"file": ("splash.png", png_bytes, "image/png")}
    headers = await auth_headers(db_session, admin)
    res = await mutation_client.post(
        "/admin/media/splash",
        headers=headers,
        files=files,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["media_type"] == "image"
    assert "splashes/" in data["url"]
    assert data["url"].endswith(".webp")
    assert data["width"] == 200
    assert data["height"] == 400
    assert data["duration_seconds"] is None
    assert data["bytes"] > 0

    settings = get_settings()
    base = settings.media_public_base_url.rstrip("/") + "/"
    rel = data["url"][len(base):]
    assert rel in fake_storage.files


@pytest.mark.asyncio
async def test_admin_upload_splash_video(
    db_session: AsyncSession,
    mutation_client: AsyncClient,  # noqa: F811
    fake_storage: InMemoryMediaStorage,
):
    admin = await make_admin(db_session, "superadmin", None, "super_vid")
    video_bytes = make_mp4(duration_sec=3.0, width=1080, height=1920)
    files = {"file": ("splash.mp4", video_bytes, "video/mp4")}
    headers = await auth_headers(db_session, admin)
    res = await mutation_client.post(
        "/admin/media/splash",
        headers=headers,
        files=files,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["media_type"] == "video"
    assert "splashes/" in data["url"]
    assert data["url"].endswith(".mp4")
    assert data["width"] == 1080
    assert data["height"] == 1920
    assert data["duration_seconds"] == 3.0

    settings = get_settings()
    base = settings.media_public_base_url.rstrip("/") + "/"
    rel = data["url"][len(base):]
    assert rel in fake_storage.files


@pytest.mark.asyncio
async def test_admin_upload_splash_video_rejects_audio_and_over_duration(
    db_session: AsyncSession,
    mutation_client: AsyncClient,  # noqa: F811
    fake_storage: InMemoryMediaStorage,
):
    admin = await make_admin(db_session, "superadmin", None, "super_vid_rej")
    headers = await auth_headers(db_session, admin)

    # Audio track present
    audio_video = make_mp4(duration_sec=2.0, include_audio=True)
    res = await mutation_client.post(
        "/admin/media/splash",
        headers=headers,
        files={"file": ("splash.mp4", audio_video, "video/mp4")},
    )
    assert res.status_code == 422
    assert "звук запрещён" in res.json()["error"]["message"]

    # Duration > 5.0 seconds
    long_video = make_mp4(duration_sec=5.5)
    res = await mutation_client.post(
        "/admin/media/splash",
        headers=headers,
        files={"file": ("splash.mp4", long_video, "video/mp4")},
    )
    assert res.status_code == 422
    assert "превышает лимит 5 секунд" in res.json()["error"]["message"]


@pytest.mark.asyncio
async def test_admin_upload_splash_manager_scoping(
    db_session: AsyncSession,
    mutation_client: AsyncClient,  # noqa: F811
    fake_storage: InMemoryMediaStorage,
):
    biz1 = await make_business(db_session, "Biz 1")
    biz2 = await make_business(db_session, "Biz 2")
    manager1 = await make_admin(db_session, "business_manager", biz1.id, "mgr_scope")
    headers = await auth_headers(db_session, manager1)

    png_bytes = _make_png(100, 100)

    # Manager attempting to upload for another business
    res = await mutation_client.post(
        "/admin/media/splash",
        headers=headers,
        files={"file": ("splash.png", png_bytes, "image/png")},
        data={"business_id": str(biz2.id)},
    )
    assert res.status_code == 403

    # Manager uploading for own business
    res = await mutation_client.post(
        "/admin/media/splash",
        headers=headers,
        files={"file": ("splash.png", png_bytes, "image/png")},
        data={"business_id": str(biz1.id)},
    )
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_business_splash_config_crud_and_scoping(
    db_session: AsyncSession,
    mutation_client: AsyncClient,  # noqa: F811
    fake_storage: InMemoryMediaStorage,
):
    biz1 = await make_business(db_session, "Keremet Store")
    biz2 = await make_business(db_session, "Other Store")
    manager1 = await make_admin(db_session, "business_manager", biz1.id, "mgr_crud")
    headers = await auth_headers(db_session, manager1)

    # 1. Default config: enabled=False
    res = await mutation_client.get(
        f"/admin/businesses/{biz1.id}/splash",
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["enabled"] is False

    # 2. Manager cannot access biz2 splash (returns 404 to avoid enumeration)
    res = await mutation_client.get(
        f"/admin/businesses/{biz2.id}/splash",
        headers=headers,
    )
    assert res.status_code == 404

    # 3. Enable splash with valid media URL
    settings = get_settings()
    base = settings.media_public_base_url.rstrip("/") + "/"
    media_url = f"{base}splashes/11111111111111111111111111111111.webp"
    fake_storage.files["splashes/11111111111111111111111111111111.webp"] = b"fake"

    update_payload = {
        "enabled": True,
        "media_type": "image",
        "media_url": media_url,
        "width": 1080,
        "height": 1920,
        "duration_seconds": None,
        "file_size": 250000,
    }
    res = await mutation_client.put(
        f"/admin/businesses/{biz1.id}/splash",
        headers=headers,
        json=update_payload,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["enabled"] is True
    assert data["media_type"] == "image"
    assert data["media_url"] == media_url
    assert data["version"] is not None

    # Check audit log
    audit_entry = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.business_id == biz1.id,
            AuditLog.action == "business_splash_updated",
        )
    )
    assert audit_entry is not None

    # 4. SSRF protection: reject external arbitrary URLs
    bad_payload = {
        "enabled": True,
        "media_type": "image",
        "media_url": "https://evil.attacker.com/exploit.png",
    }
    res = await mutation_client.put(
        f"/admin/businesses/{biz1.id}/splash",
        headers=headers,
        json=bad_payload,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_public_app_splash_endpoint(
    db_session: AsyncSession,
    mutation_client: AsyncClient,  # noqa: F811
    fake_storage: InMemoryMediaStorage,
):
    biz = await make_business(db_session, "Keremet")
    biz.android_app_id = "kz.cashbackone.keremet"
    settings = get_settings()
    base = settings.media_public_base_url.rstrip("/") + "/"
    media_url = f"{base}splashes/22222222222222222222222222222222.webp"
    biz.splash_config = {
        "enabled": True,
        "media_type": "image",
        "media_url": media_url,
        "width": 1080,
        "height": 1920,
        "duration_seconds": None,
        "file_size": 150000,
        "version": "v1token",
    }
    await db_session.commit()

    # 1. Query by app_id without authentication
    res = await mutation_client.get("/public/app-splash?app_id=kz.cashbackone.keremet")
    assert res.status_code == 200
    data = res.json()
    assert data["enabled"] is True
    assert data["business_id"] == str(biz.id)
    assert data["media_url"] == media_url
    assert "ETag" in res.headers

    # 2. Test ETag caching (304 Not Modified)
    etag = res.headers["ETag"]
    res_cached = await mutation_client.get(
        "/public/app-splash?app_id=kz.cashbackone.keremet",
        headers={"if-none-match": etag},
    )
    assert res_cached.status_code == 304

    # 3. Query with non-existent app_id returns enabled=False (200 OK)
    res_none = await mutation_client.get("/public/app-splash?app_id=kz.unknown.app")
    assert res_none.status_code == 200
    assert res_none.json()["enabled"] is False
