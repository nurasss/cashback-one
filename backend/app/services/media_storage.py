import asyncio
import io
import logging
import posixpath
import re
import ssl
import uuid
from abc import ABC, abstractmethod
from ftplib import FTP_TLS, all_errors, error_perm
from typing import Any

from sqlalchemy import func, select

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.models.entities import Business, Promotion

logger = logging.getLogger(__name__)

SAFE_MEDIA_PATH_REGEX = re.compile(r"^(promotions|logos)/[0-9a-f]{32}\.webp$")
FTPS_OPERATION_ERRORS = (*all_errors, ssl.SSLError, ValueError)
CLEANUP_ERRORS = (*all_errors, ssl.SSLError, AppError, ValueError)


class MediaStorage(ABC):
    """Abstract interface for image and media storage."""

    @abstractmethod
    async def put(self, relative_path: str, data: bytes) -> None:
        """Store bytes at relative_path (e.g. 'promotions/<id>.webp')."""

    @abstractmethod
    async def delete(self, relative_path: str) -> None:
        """Delete file at relative_path (e.g. 'promotions/<id>.webp')."""


class DisabledMediaStorage(MediaStorage):
    """Fallback storage used when FTPS hosting is not configured."""

    async def put(self, relative_path: str, data: bytes) -> None:
        raise AppError(
            "MEDIA_STORAGE_NOT_CONFIGURED",
            "Media storage is not configured on this server.",
            status_code=503,
        )

    async def delete(self, relative_path: str) -> None:
        logger.info("Skipping deletion of %s: media storage is not configured", relative_path)


class InMemoryMediaStorage(MediaStorage):
    """In-memory media storage for unit and integration tests."""

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.fail_put: bool = False
        self.fail_delete: bool = False

    async def put(self, relative_path: str, data: bytes) -> None:
        if not SAFE_MEDIA_PATH_REGEX.match(relative_path):
            raise ValueError(f"Path outside allowed media directory: {relative_path}")
        if self.fail_put:
            raise AppError("MEDIA_STORAGE_ERROR", "Simulated storage failure", status_code=502)
        self.files[relative_path] = data

    async def delete(self, relative_path: str) -> None:
        if not SAFE_MEDIA_PATH_REGEX.match(relative_path):
            raise ValueError(f"Path outside allowed media directory: {relative_path}")
        if self.fail_delete:
            raise AppError("MEDIA_STORAGE_ERROR", "Simulated storage delete failure", status_code=502)
        self.files.pop(relative_path, None)


class FTPSMediaStorage(MediaStorage):
    """FTPS storage implementation targeting hosting root over FTP_TLS."""

    def __init__(
        self,
        *,
        host: str,
        port: int = 21,
        user: str,
        password: str,
        root_dir: str = "",
        timeout: float = 20.0,
    ) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.root_dir = root_dir.strip()
        self.timeout = timeout

    def _create_ftps_client(self) -> FTP_TLS:
        # TLS with strict certificate verification; the hosting FTPS drops data
        # transfers above TLS 1.2 (see docs/DEPLOY_VPS.md), so cap the version.
        context = ssl.create_default_context()
        context.maximum_version = ssl.TLSVersion.TLSv1_2
        ftps = FTP_TLS(context=context, timeout=self.timeout)
        ftps.connect(self.host, self.port, timeout=self.timeout)
        ftps.login(self.user, self.password)
        ftps.prot_p()  # Secure data connection
        ftps.voidcmd("TYPE I")  # Binary transfer mode
        return ftps

    def _ensure_dir(self, ftps: FTP_TLS, target_dir: str) -> None:
        """Walk into target_dir one segment at a time, creating missing ones.

        Each step is relative to the directory entered by the previous step, so
        the connection ends up inside target_dir.
        """
        if target_dir.startswith("/"):
            ftps.cwd("/")
        for part in (p for p in target_dir.split("/") if p):
            try:
                ftps.cwd(part)
            except error_perm:
                ftps.mkd(part)
                ftps.cwd(part)

    def _sync_put(self, relative_path: str, data: bytes) -> None:
        category, filename = relative_path.split("/")
        remote_dir = posixpath.join(self.root_dir, "media", category)
        temp_filename = f"{filename}.tmp.{uuid.uuid4().hex}"

        ftps: FTP_TLS | None = None
        try:
            ftps = self._create_ftps_client()
            self._ensure_dir(ftps, remote_dir)

            bio = io.BytesIO(data)
            ftps.storbinary(f"STOR {temp_filename}", bio)

            # Validate size of uploaded temporary file
            try:
                uploaded_size = ftps.size(temp_filename)
            except FTPS_OPERATION_ERRORS:
                uploaded_size = None

            if uploaded_size is not None and uploaded_size != len(data):
                try:
                    ftps.delete(temp_filename)
                except FTPS_OPERATION_ERRORS:
                    logger.debug("Could not cleanup temp file after size mismatch: %s", temp_filename)
                raise AppError(
                    "MEDIA_STORAGE_ERROR",
                    "Uploaded file size mismatch on hosting storage.",
                    status_code=502,
                )

            # Atomic rename from temporary file to final target
            ftps.rename(temp_filename, filename)
            try:
                ftps.quit()
            except FTPS_OPERATION_ERRORS:
                logger.debug("FTPS quit failed softly")
        except AppError:
            raise
        except FTPS_OPERATION_ERRORS as exc:
            logger.error("FTPS upload operation failed: %s", type(exc).__name__)
            if ftps is not None:
                try:
                    ftps.close()
                except FTPS_OPERATION_ERRORS:
                    logger.debug("FTPS close failed softly")
            raise AppError(
                "MEDIA_STORAGE_ERROR",
                "Failed to store media file on remote hosting.",
                status_code=502,
            ) from None

    def _sync_delete(self, relative_path: str) -> None:
        category, filename = relative_path.split("/")
        remote_dir = posixpath.join(self.root_dir, "media", category)

        ftps: FTP_TLS | None = None
        try:
            ftps = self._create_ftps_client()
            try:
                ftps.cwd(remote_dir)
                ftps.delete(filename)
            except error_perm as perm_err:
                logger.info("FTPS delete notice for %s: %s", relative_path, perm_err)
            try:
                ftps.quit()
            except FTPS_OPERATION_ERRORS:
                logger.debug("FTPS quit failed softly")
        except FTPS_OPERATION_ERRORS as exc:
            logger.error("FTPS delete operation failed: %s", type(exc).__name__)
            if ftps is not None:
                try:
                    ftps.close()
                except FTPS_OPERATION_ERRORS:
                    logger.debug("FTPS close failed softly")
            raise AppError(
                "MEDIA_STORAGE_ERROR",
                "Failed to delete media file on remote hosting.",
                status_code=502,
            ) from None

    async def put(self, relative_path: str, data: bytes) -> None:
        if not SAFE_MEDIA_PATH_REGEX.match(relative_path):
            raise ValueError(f"Path outside allowed media directory: {relative_path}")
        await asyncio.to_thread(self._sync_put, relative_path, data)

    async def delete(self, relative_path: str) -> None:
        if not SAFE_MEDIA_PATH_REGEX.match(relative_path):
            raise ValueError(f"Path outside allowed media directory: {relative_path}")
        await asyncio.to_thread(self._sync_delete, relative_path)


def get_media_storage() -> MediaStorage:
    current_settings = get_settings()
    if not current_settings.is_media_storage_configured:
        return DisabledMediaStorage()

    return FTPSMediaStorage(
        host=current_settings.media_ftps_host,
        port=current_settings.media_ftps_port,
        user=current_settings.media_ftps_user,
        password=current_settings.media_ftps_password.get_secret_value(),
        root_dir=current_settings.media_ftps_root_dir,
    )


async def maybe_cleanup_old_media_file(
    db: Any,
    storage: MediaStorage,
    old_url: str | None,
    settings: Settings,
) -> None:
    """Best-effort cleanup for replaced or deleted media files.

    Strictly checks that the URL points to our MEDIA_PUBLIC_BASE_URL,
    matches ^(promotions|logos)/[0-9a-f]{32}\\.webp$, and is not referenced by
    any other promotion or business in the database.
    """
    if not old_url:
        return
    base = settings.media_public_base_url.rstrip("/") + "/"
    if not old_url.startswith(base):
        return
    rel_path = old_url[len(base):]
    if not SAFE_MEDIA_PATH_REGEX.match(rel_path):
        return

    try:
        promo_count = await db.scalar(
            select(func.count()).select_from(Promotion).where(Promotion.image_url == old_url)
        )
        biz_count = await db.scalar(
            select(func.count()).select_from(Business).where(Business.logo_url == old_url)
        )
        if (promo_count or 0) > 0 or (biz_count or 0) > 0:
            return

        await storage.delete(rel_path)
    except CLEANUP_ERRORS as exc:
        logger.warning("Failed to cleanup orphaned media file %s: %s", rel_path, exc)
