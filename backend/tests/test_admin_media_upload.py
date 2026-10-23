"""Tests for admin image upload, WebP conversion, storage, and cleanup."""
import ftplib
import io
import posixpath
import ssl
import uuid

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.main import app
from app.models.entities import AuditLog
from app.services.media_storage import (
    SAFE_MEDIA_PATH_REGEX,
    FTPSMediaStorage,
    InMemoryMediaStorage,
    get_media_storage,
    maybe_cleanup_old_media_file,
)
from tests.test_admin_mutations import (  # noqa: F401
    ORIGIN_HEADERS,
    auth_headers,
    make_admin,
    make_business,
    mutation_client,
)


def _make_jpeg_with_exif() -> bytes:
    # 200x100 image with orientation=6 (rotated 90 CW) and sample GPS
    im = Image.new("RGB", (200, 100), color=(255, 0, 0))
    exif = im.getexif()
    exif[0x0112] = 6  # Orientation = 6 (transposed 90 CW)
    # GPS IFD tag 0x8825
    exif[0x010E] = "Sample description with GPS test"
    bio = io.BytesIO()
    im.save(bio, format="JPEG", exif=exif)
    return bio.getvalue()


def _make_rgba_png() -> bytes:
    im = Image.new("RGBA", (100, 100), color=(0, 255, 0, 128))
    bio = io.BytesIO()
    im.save(bio, format="PNG")
    return bio.getvalue()


def _make_large_image(w: int, h: int) -> bytes:
    im = Image.new("RGB", (w, h), color=(0, 0, 255))
    bio = io.BytesIO()
    im.save(bio, format="JPEG")
    return bio.getvalue()


@pytest.fixture
def fake_storage() -> InMemoryMediaStorage:
    storage = InMemoryMediaStorage()
    app.dependency_overrides[get_media_storage] = lambda: storage
    yield storage
    app.dependency_overrides.pop(get_media_storage, None)


@pytest.mark.asyncio
async def test_upload_without_token_returns_401(
    mutation_client: AsyncClient,  # noqa: F811
) -> None:
    res = await mutation_client.post(
        "/admin/media/images",
        headers=ORIGIN_HEADERS,
        data={"purpose": "promotion"},
        files={"file": ("test.jpg", b"dummy", "image/jpeg")},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_upload_jpeg_with_exif_transposes_and_strips_metadata(
    db_session: AsyncSession,
    mutation_client: AsyncClient,  # noqa: F811
    fake_storage: InMemoryMediaStorage,
) -> None:
    admin = await make_admin(db_session, "superadmin", None, "upload-super")
    headers = await auth_headers(db_session, admin)
    await db_session.commit()

    jpeg_data = _make_jpeg_with_exif()
    res = await mutation_client.post(
        "/admin/media/images",
        headers=headers,
        data={"purpose": "promotion"},
        files={"file": ("photo.jpg", jpeg_data, "image/jpeg")},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["url"].startswith("https://cashback-qr.poscenter.kz/media/promotions/")
    assert body["url"].endswith(".webp")

    # Due to Orientation=6 (90 CW), width and height are transposed: 200x100 -> 100x200
    assert body["width"] == 100
    assert body["height"] == 200

    # Extract stored bytes from in-memory storage
    rel_path = body["url"].replace("https://cashback-qr.poscenter.kz/media/", "")
    stored_bytes = fake_storage.files[rel_path]
    stored_im = Image.open(io.BytesIO(stored_bytes))
    assert stored_im.format == "WEBP"
    # Ensure no EXIF metadata remains
    assert "exif" not in stored_im.info

    # Check audit log
    audit_entry = await db_session.scalar(
        select(AuditLog).where(AuditLog.action == "media_uploaded").order_by(AuditLog.created_at.desc())
    )
    assert audit_entry is not None
    assert audit_entry.actor == admin.login
    assert audit_entry.after_state["purpose"] == "promotion"
    assert audit_entry.after_state["bytes"] == len(stored_bytes)


@pytest.mark.asyncio
async def test_upload_png_with_alpha_preserves_alpha(
    db_session: AsyncSession,
    mutation_client: AsyncClient,  # noqa: F811
    fake_storage: InMemoryMediaStorage,
) -> None:
    admin = await make_admin(db_session, "superadmin", None, "png-super")
    headers = await auth_headers(db_session, admin)
    await db_session.commit()

    png_data = _make_rgba_png()
    res = await mutation_client.post(
        "/admin/media/images",
        headers=headers,
        data={"purpose": "logo"},
        files={"file": ("logo.png", png_data, "image/png")},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["url"].startswith("https://cashback-qr.poscenter.kz/media/logos/")

    rel_path = body["url"].replace("https://cashback-qr.poscenter.kz/media/", "")
    stored_bytes = fake_storage.files[rel_path]
    stored_im = Image.open(io.BytesIO(stored_bytes))
    assert stored_im.format == "WEBP"
    assert stored_im.mode == "RGBA"


@pytest.mark.asyncio
async def test_upload_large_image_downscaled_properly(
    db_session: AsyncSession,
    mutation_client: AsyncClient,  # noqa: F811
    fake_storage: InMemoryMediaStorage,
) -> None:
    admin = await make_admin(db_session, "superadmin", None, "scale-super")
    headers = await auth_headers(db_session, admin)
    await db_session.commit()

    large_data = _make_large_image(2400, 1200)

    # 1. Promotion downscaled to max 1600: 2400x1200 -> 1600x800
    res_promo = await mutation_client.post(
        "/admin/media/images",
        headers=headers,
        data={"purpose": "promotion"},
        files={"file": ("large.jpg", large_data, "image/jpeg")},
    )
    assert res_promo.status_code == 200
    assert res_promo.json()["width"] == 1600
    assert res_promo.json()["height"] == 800

    # 2. Logo downscaled to max 512: 2400x1200 -> 512x256
    res_logo = await mutation_client.post(
        "/admin/media/images",
        headers=headers,
        data={"purpose": "logo"},
        files={"file": ("large.jpg", large_data, "image/jpeg")},
    )
    assert res_logo.status_code == 200
    assert res_logo.json()["width"] == 512
    assert res_logo.json()["height"] == 256


@pytest.mark.asyncio
async def test_upload_text_file_as_jpg_returns_415(
    db_session: AsyncSession,
    mutation_client: AsyncClient,  # noqa: F811
    fake_storage: InMemoryMediaStorage,
) -> None:
    admin = await make_admin(db_session, "superadmin", None, "text-super")
    headers = await auth_headers(db_session, admin)
    await db_session.commit()

    res = await mutation_client.post(
        "/admin/media/images",
        headers=headers,
        data={"purpose": "promotion"},
        files={"file": ("not_an_image.jpg", b"This is plain text pretending to be JPEG", "image/jpeg")},
    )
    assert res.status_code == 415
    assert res.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


@pytest.mark.asyncio
async def test_upload_file_exceeding_limit_returns_413(
    db_session: AsyncSession,
    mutation_client: AsyncClient,  # noqa: F811
    fake_storage: InMemoryMediaStorage,
) -> None:
    admin = await make_admin(db_session, "superadmin", None, "limit-super")
    headers = await auth_headers(db_session, admin)
    await db_session.commit()

    # Create dummy stream larger than limit (default limit in settings is 10MB)
    # We temporarily set max_upload_bytes = 1024 for quick testing
    settings = get_settings()
    orig_limit = settings.media_max_upload_bytes
    settings.media_max_upload_bytes = 1000
    try:
        big_bytes = b"x" * 1500
        res = await mutation_client.post(
            "/admin/media/images",
            headers=headers,
            data={"purpose": "promotion"},
            files={"file": ("big.jpg", big_bytes, "image/jpeg")},
        )
        assert res.status_code == 413
        assert res.json()["error"]["code"] == "FILE_TOO_LARGE"
    finally:
        settings.media_max_upload_bytes = orig_limit


@pytest.mark.asyncio
async def test_upload_decompression_bomb_returns_413_not_500(
    db_session: AsyncSession,
    mutation_client: AsyncClient,  # noqa: F811
    fake_storage: InMemoryMediaStorage,
) -> None:
    admin = await make_admin(db_session, "superadmin", None, "bomb-super")
    headers = await auth_headers(db_session, admin)
    await db_session.commit()

    # Image with pixels > MAX_IMAGE_PIXELS (40M pixels, e.g. 7000x7000 = 49M pixels)
    # We can create a tiny 1-bit or indexed palette image that expands to 49M pixels
    im = Image.new("1", (7000, 7000), 0)
    bio = io.BytesIO()
    im.save(bio, format="PNG")
    bomb_data = bio.getvalue()

    res = await mutation_client.post(
        "/admin/media/images",
        headers=headers,
        data={"purpose": "promotion"},
        files={"file": ("bomb.png", bomb_data, "image/png")},
    )
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "IMAGE_TOO_LARGE"


@pytest.mark.asyncio
async def test_upload_storage_failure_returns_502_without_leaks(
    db_session: AsyncSession,
    mutation_client: AsyncClient,  # noqa: F811
    fake_storage: InMemoryMediaStorage,
) -> None:
    admin = await make_admin(db_session, "superadmin", None, "fail-super")
    headers = await auth_headers(db_session, admin)
    await db_session.commit()

    fake_storage.fail_put = True
    png_data = _make_rgba_png()
    res = await mutation_client.post(
        "/admin/media/images",
        headers=headers,
        data={"purpose": "promotion"},
        files={"file": ("promo.png", png_data, "image/png")},
    )
    assert res.status_code == 502
    assert res.json()["error"]["code"] == "MEDIA_STORAGE_ERROR"
    # Ensure no internal path or credentials leaked
    assert "password" not in res.text.lower()
    assert "ftps" not in res.text.lower()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raised_exc,secret_probe",
    [
        (ConnectionRefusedError("Connection refused to 127.0.0.1:21"), "127.0.0.1"),
        (ftplib.error_perm("530 Login authentication failed for secret_user"), "secret_user"),
        (ssl.SSLCertVerificationError("certificate verify failed: self signed certificate"), "self signed"),
    ],
)
async def test_ftps_connection_failure_on_upload_returns_502_without_leak(
    raised_exc: Exception,
    secret_probe: str,
    db_session: AsyncSession,
    mutation_client: AsyncClient,  # noqa: F811
) -> None:
    admin = await make_admin(db_session, "superadmin", None, "ftps-fail-admin")
    headers = await auth_headers(db_session, admin)
    await db_session.commit()

    storage = FTPSMediaStorage(
        host="test-ftp.example",
        port=21,
        user="test_user",
        password="secret_password_123",
        root_dir="/test",
    )

    def _mock_create() -> ftplib.FTP_TLS:
        raise raised_exc

    storage._create_ftps_client = _mock_create  # type: ignore[method-assign]

    app.dependency_overrides[get_media_storage] = lambda: storage
    try:
        png_data = _make_rgba_png()
        res = await mutation_client.post(
            "/admin/media/images",
            headers=headers,
            data={"purpose": "promotion"},
            files={"file": ("promo.png", png_data, "image/png")},
        )
        assert res.status_code == 502
        assert res.json()["error"]["code"] == "MEDIA_STORAGE_ERROR"
        # Exception details and secrets must not leak
        assert secret_probe not in res.text
        assert "secret_password" not in res.text
    finally:
        app.dependency_overrides.pop(get_media_storage, None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raised_exc",
    [
        ConnectionRefusedError("Connection refused to 127.0.0.1:21"),
        ftplib.error_perm("530 Login authentication failed"),
        ssl.SSLCertVerificationError("certificate verify failed"),
    ],
)
async def test_ftps_connection_failure_on_delete_succeeds_with_warning(
    raised_exc: Exception,
    db_session: AsyncSession,
) -> None:
    storage = FTPSMediaStorage(
        host="test-ftp.example",
        port=21,
        user="test_user",
        password="secret_password_123",
        root_dir="/test",
    )

    def _mock_create() -> ftplib.FTP_TLS:
        raise raised_exc

    storage._create_ftps_client = _mock_create  # type: ignore[method-assign]

    settings = get_settings()
    orphaned_url = f"{settings.media_public_base_url}/promotions/{'a' * 32}.webp"

    # maybe_cleanup_old_media_file must NOT raise any error even if storage connection fails completely
    await maybe_cleanup_old_media_file(db_session, storage, orphaned_url, settings)


@pytest.mark.asyncio
async def test_upload_when_ftps_not_configured_returns_503(
    db_session: AsyncSession,
    mutation_client: AsyncClient,  # noqa: F811
) -> None:
    admin = await make_admin(db_session, "superadmin", None, "disabled-super")
    headers = await auth_headers(db_session, admin)
    await db_session.commit()

    # Ensure get_media_storage override is cleared to use real unconfigured state
    app.dependency_overrides.pop(get_media_storage, None)
    settings = get_settings()
    settings.media_ftps_host = ""
    settings.media_ftps_user = ""

    png_data = _make_rgba_png()
    res = await mutation_client.post(
        "/admin/media/images",
        headers=headers,
        data={"purpose": "promotion"},
        files={"file": ("promo.png", png_data, "image/png")},
    )
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "MEDIA_STORAGE_NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_filename_independent_of_user_input(
    db_session: AsyncSession,
    mutation_client: AsyncClient,  # noqa: F811
    fake_storage: InMemoryMediaStorage,
) -> None:
    admin = await make_admin(db_session, "superadmin", None, "name-super")
    headers = await auth_headers(db_session, admin)
    await db_session.commit()

    png_data = _make_rgba_png()
    # Evil user input filename with path traversal
    res = await mutation_client.post(
        "/admin/media/images",
        headers=headers,
        data={"purpose": "promotion"},
        files={"file": ("../../../etc/passwd.png", png_data, "image/png")},
    )
    assert res.status_code == 200
    url = res.json()["url"]
    assert "passwd" not in url
    assert ".." not in url
    rel_path = url.replace("https://cashback-qr.poscenter.kz/media/", "")
    assert SAFE_MEDIA_PATH_REGEX.match(rel_path)


@pytest.mark.asyncio
async def test_media_cleanup_on_promotion_update_and_delete(
    db_session: AsyncSession,
    mutation_client: AsyncClient,  # noqa: F811
    fake_storage: InMemoryMediaStorage,
) -> None:
    admin = await make_admin(db_session, "superadmin", None, "clean-super")
    headers = await auth_headers(db_session, admin)
    await db_session.commit()

    # Put an initial image in fake storage
    old_id = uuid.uuid4().hex
    old_rel = f"promotions/{old_id}.webp"
    old_url = f"https://cashback-qr.poscenter.kz/media/{old_rel}"
    await fake_storage.put(old_rel, b"old-content")

    # Create promotion with old_url
    res = await mutation_client.post(
        "/admin/promotions",
        headers=headers,
        json={"kind": "banner", "title": "Cleanup Test", "image_url": old_url},
    )
    assert res.status_code == 201
    promo_id = res.json()["id"]

    # 1. Update promotion with a new URL -> old image should be deleted from storage
    new_id = uuid.uuid4().hex
    new_rel = f"promotions/{new_id}.webp"
    new_url = f"https://cashback-qr.poscenter.kz/media/{new_rel}"
    await fake_storage.put(new_rel, b"new-content")

    patch_res = await mutation_client.patch(
        f"/admin/promotions/{promo_id}",
        headers=headers,
        json={"image_url": new_url},
    )
    assert patch_res.status_code == 200
    assert old_rel not in fake_storage.files
    assert new_rel in fake_storage.files

    # 2. Delete promotion -> new image should be deleted from storage
    del_res = await mutation_client.delete(
        f"/admin/promotions/{promo_id}",
        headers=headers,
    )
    assert del_res.status_code == 204
    assert new_rel not in fake_storage.files


@pytest.mark.asyncio
async def test_media_cleanup_does_not_touch_external_or_unsafe_paths(
    db_session: AsyncSession,
    fake_storage: InMemoryMediaStorage,
) -> None:
    settings = get_settings()

    # 1. External URL (not our domain)
    await maybe_cleanup_old_media_file(
        db_session, fake_storage, "https://external.cdn/promotions/abc.webp", settings
    )
    # 2. Path with directory traversal or outside allowed folders
    await maybe_cleanup_old_media_file(
        db_session, fake_storage, f"{settings.media_public_base_url}/../index.html", settings
    )
    await maybe_cleanup_old_media_file(
        db_session, fake_storage, f"{settings.media_public_base_url}/other/abc.webp", settings
    )
    # Storage should remain unaffected
    assert len(fake_storage.files) == 0


@pytest.mark.asyncio
async def test_media_cleanup_preserves_shared_file(
    db_session: AsyncSession,
    mutation_client: AsyncClient,  # noqa: F811
    fake_storage: InMemoryMediaStorage,
) -> None:
    admin = await make_admin(db_session, "superadmin", None, "shared-super")
    headers = await auth_headers(db_session, admin)
    await db_session.commit()

    shared_id = uuid.uuid4().hex
    shared_rel = f"promotions/{shared_id}.webp"
    shared_url = f"https://cashback-qr.poscenter.kz/media/{shared_rel}"
    await fake_storage.put(shared_rel, b"shared-image")

    # Two promotions use the exact same image
    p1 = await mutation_client.post(
        "/admin/promotions", headers=headers, json={"kind": "banner", "title": "Promo 1", "image_url": shared_url}
    )
    p2 = await mutation_client.post(
        "/admin/promotions", headers=headers, json={"kind": "banner", "title": "Promo 2", "image_url": shared_url}
    )
    assert p1.status_code == 201 and p2.status_code == 201

    # Delete Promo 1 -> file must NOT be deleted because Promo 2 still references it!
    del_res = await mutation_client.delete(f"/admin/promotions/{p1.json()['id']}", headers=headers)
    assert del_res.status_code == 204
    assert shared_rel in fake_storage.files

    # Delete Promo 2 -> now nobody references it, file should be deleted!
    del_res2 = await mutation_client.delete(f"/admin/promotions/{p2.json()['id']}", headers=headers)
    assert del_res2.status_code == 204
    assert shared_rel not in fake_storage.files


class _FakeFTPServer:
    """Minimal FTP model with a working directory, like the hosting server."""

    def __init__(self, dirs: set[str]) -> None:
        self.dirs = set(dirs) | {"/"}
        self.files: dict[str, bytes] = {}
        self.cwd_path = "/"

    def _abs(self, path: str) -> str:
        return posixpath.normpath(posixpath.join(self.cwd_path, path))

    def cwd(self, path: str) -> None:
        target = self._abs(path)
        if target not in self.dirs:
            raise ftplib.error_perm(f"550 {path}: No such file or directory")
        self.cwd_path = target

    def mkd(self, path: str) -> None:
        target = self._abs(path)
        if posixpath.dirname(target) not in self.dirs or target in self.dirs:
            raise ftplib.error_perm(f"550 {path}: cannot create")
        self.dirs.add(target)

    def storbinary(self, cmd: str, fp: io.BytesIO) -> None:
        self.files[self._abs(cmd.split(" ", 1)[1])] = fp.read()

    def size(self, name: str) -> int:
        return len(self.files[self._abs(name)])

    def rename(self, src: str, dst: str) -> None:
        self.files[self._abs(dst)] = self.files.pop(self._abs(src))

    def delete(self, name: str) -> None:
        if self.files.pop(self._abs(name), None) is None:
            raise ftplib.error_perm(f"550 {name}: No such file")

    def quit(self) -> None:
        pass

    def close(self) -> None:
        pass


@pytest.mark.asyncio
async def test_ftps_put_creates_nested_dirs_under_relative_site_root() -> None:
    server = _FakeFTPServer({"/site"})
    storage = FTPSMediaStorage(host="h", user="u", password="p", root_dir="site")

    def _connect() -> _FakeFTPServer:
        server.cwd_path = "/"
        return server

    storage._create_ftps_client = _connect  # type: ignore[method-assign,assignment]

    first = f"promotions/{'a' * 32}.webp"
    second = f"promotions/{'b' * 32}.webp"
    await storage.put(first, b"one")
    await storage.put(second, b"two")

    assert {"/site/media", "/site/media/promotions"} <= server.dirs
    assert server.files == {
        f"/site/media/{first}": b"one",
        f"/site/media/{second}": b"two",
    }

    await storage.delete(first)
    assert set(server.files) == {f"/site/media/{second}"}
