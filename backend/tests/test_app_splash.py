"""Integration tests for app splash management, upload, storage scoping, public endpoint, and app-content."""
import io
import pathlib

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.main import app
from app.models.entities import AuditLog, BusinessSplashAsset
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

FIXTURE_PATH = pathlib.Path(__file__).parent / "fixtures" / "sample_splash.mp4"


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
    biz = await make_business(db_session, "Biz Splash Img")
    admin = await make_admin(db_session, "superadmin", None, "super_splash")
    png_bytes = _make_png(200, 400)
    files = {"file": ("splash.png", png_bytes, "image/png")}
    headers = await auth_headers(db_session, admin)
    res = await mutation_client.post(
        "/admin/media/splash",
        headers=headers,
        files=files,
        data={"business_id": str(biz.id)},
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

    # Check asset was saved to database
    asset = await db_session.scalar(
        select(BusinessSplashAsset).where(BusinessSplashAsset.media_url == data["url"])
    )
    assert asset is not None
    assert asset.business_id == biz.id
    assert asset.media_type == "image"
    assert asset.width == 200
    assert asset.height == 400


@pytest.mark.asyncio
async def test_admin_upload_splash_video_real_fixture(
    db_session: AsyncSession,
    mutation_client: AsyncClient,  # noqa: F811
    fake_storage: InMemoryMediaStorage,
):
    biz = await make_business(db_session, "Biz Splash Vid")
    admin = await make_admin(db_session, "superadmin", None, "super_vid")
    assert FIXTURE_PATH.is_file(), f"Fixture {FIXTURE_PATH} must exist"
    video_bytes = FIXTURE_PATH.read_bytes()
    files = {"file": ("splash.mp4", video_bytes, "video/mp4")}
    headers = await auth_headers(db_session, admin)
    res = await mutation_client.post(
        "/admin/media/splash",
        headers=headers,
        files=files,
        data={"business_id": str(biz.id)},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["media_type"] == "video"
    assert "splashes/" in data["url"]
    assert data["url"].endswith(".mp4")
    assert data["width"] == 320
    assert data["height"] == 240
    assert data["duration_seconds"] == 1.0

    settings = get_settings()
    base = settings.media_public_base_url.rstrip("/") + "/"
    rel = data["url"][len(base):]
    assert rel in fake_storage.files

    # Check asset saved in DB
    asset = await db_session.scalar(
        select(BusinessSplashAsset).where(BusinessSplashAsset.media_url == data["url"])
    )
    assert asset is not None
    assert asset.business_id == biz.id
    assert asset.media_type == "video"
    assert asset.duration_seconds == 1.0


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
    long_video = make_mp4(duration_sec=5.05)
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

    # 1. Manager tries to upload explicitly for another business -> 403
    res = await mutation_client.post(
        "/admin/media/splash",
        headers=headers,
        files={"file": ("splash.png", png_bytes, "image/png")},
        data={"business_id": str(biz2.id)},
    )
    assert res.status_code == 403

    # 2. Manager uploads without specifying business_id -> automatically scoped to own business
    res = await mutation_client.post(
        "/admin/media/splash",
        headers=headers,
        files={"file": ("splash.png", png_bytes, "image/png")},
    )
    assert res.status_code == 200
    url = res.json()["url"]

    asset = await db_session.scalar(
        select(BusinessSplashAsset).where(BusinessSplashAsset.media_url == url)
    )
    assert asset is not None
    assert asset.business_id == biz1.id


@pytest.mark.asyncio
async def test_business_splash_asset_ownership_and_server_metadata(
    db_session: AsyncSession,
    mutation_client: AsyncClient,  # noqa: F811
    fake_storage: InMemoryMediaStorage,
):
    biz1 = await make_business(db_session, "Owner Biz 1")
    biz2 = await make_business(db_session, "Owner Biz 2")

    manager1 = await make_admin(db_session, "business_manager", biz1.id, "mgr_own_1")
    manager2 = await make_admin(db_session, "business_manager", biz2.id, "mgr_own_2")
    headers1 = await auth_headers(db_session, manager1)
    headers2 = await auth_headers(db_session, manager2)

    # 1. Manager 1 uploads asset
    png_bytes = _make_png(300, 600)
    upload_res = await mutation_client.post(
        "/admin/media/splash",
        headers=headers1,
        files={"file": ("splash.png", png_bytes, "image/png")},
    )
    assert upload_res.status_code == 200
    asset_url1 = upload_res.json()["url"]
    real_w1 = upload_res.json()["width"]
    real_h1 = upload_res.json()["height"]
    real_bytes1 = upload_res.json()["bytes"]

    # 2. Manager 2 attempts to assign Manager 1's asset URL to Biz 2 -> 403 FORBIDDEN
    res_stolen = await mutation_client.put(
        f"/admin/businesses/{biz2.id}/splash",
        headers=headers2,
        json={"enabled": True, "media_url": asset_url1},
    )
    assert res_stolen.status_code == 403
    assert "принадлежит другому бизнесу" in res_stolen.json()["error"]["message"]

    # 3. Manager 2 attempts to use non-existent / fake UUID asset URL -> 404 NOT_FOUND
    settings = get_settings()
    base = settings.media_public_base_url.rstrip("/") + "/"
    fake_url = f"{base}splashes/00000000000000000000000000000000.webp"
    res_fake = await mutation_client.put(
        f"/admin/businesses/{biz2.id}/splash",
        headers=headers2,
        json={"enabled": True, "media_url": fake_url},
    )
    assert res_fake.status_code == 404
    assert "не найден на сервере" in res_fake.json()["error"]["message"]

    # 4. Manager 2 attempts disabled config with Manager 1's URL -> also 403 (cannot bypass check)
    res_disabled_bypass = await mutation_client.put(
        f"/admin/businesses/{biz2.id}/splash",
        headers=headers2,
        json={"enabled": False, "media_url": asset_url1},
    )
    assert res_disabled_bypass.status_code == 403

    # 5. Manager 1 saves with spoofed client fields (e.g. width=99999, height=88888, file_size=1)
    spoofed_payload = {
        "enabled": True,
        "media_type": "video",  # spoofed
        "media_url": asset_url1,
        "width": 99999,  # spoofed
        "height": 88888,  # spoofed
        "duration_seconds": 12.3,  # spoofed
        "file_size": 1,  # spoofed
    }
    res_save1 = await mutation_client.put(
        f"/admin/businesses/{biz1.id}/splash",
        headers=headers1,
        json=spoofed_payload,
    )
    assert res_save1.status_code == 200
    saved_data = res_save1.json()
    assert saved_data["enabled"] is True
    # Verified server metadata must override all client spoofing
    assert saved_data["media_type"] == "image"
    assert saved_data["width"] == real_w1
    assert saved_data["height"] == real_h1
    assert saved_data["file_size"] == real_bytes1
    assert saved_data["duration_seconds"] is None

    # Check audit log
    audit_entry = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.business_id == biz1.id,
            AuditLog.action == "business_splash_updated",
        )
    )
    assert audit_entry is not None


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
