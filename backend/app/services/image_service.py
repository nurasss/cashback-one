import io
import logging
import uuid
import warnings
from typing import Literal

from PIL import Image, ImageOps
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.models.admin import AdminUser
from app.models.entities import AuditLog
from app.schemas.admin_content import ImageUploadResponse
from app.services.admin_mutations import safe_audit_snapshot
from app.services.media_storage import MediaStorage

logger = logging.getLogger(__name__)

# Safety against decompression bomb attacks (~40 Megapixels)
MAX_IMAGE_PIXELS = 40_000_000
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}


async def process_and_store_image(
    *,
    raw_bytes: bytes,
    purpose: Literal["promotion", "logo"] | str,
    settings: Settings,
    storage: MediaStorage,
    admin: AdminUser,
    db: AsyncSession,
) -> ImageUploadResponse:
    if purpose not in ("promotion", "logo"):
        raise AppError(
            "VALIDATION_ERROR",
            "purpose must be either 'promotion' or 'logo'.",
            status_code=422,
        )

    # 1. Verify image structure with Pillow
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            probe = Image.open(io.BytesIO(raw_bytes))
            probe.verify()
            format_name = probe.format
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as bomb_err:
        logger.warning("Image decompression bomb detected: %s", bomb_err)
        raise AppError(
            "IMAGE_TOO_LARGE",
            "Image dimensions exceed safety limit.",
            status_code=413,
        ) from None
    except (Image.UnidentifiedImageError, OSError, ValueError, SyntaxError):
        raise AppError(
            "UNSUPPORTED_MEDIA_TYPE",
            "Invalid or corrupt image file.",
            status_code=415,
        ) from None

    if format_name not in ALLOWED_FORMATS:
        raise AppError(
            "UNSUPPORTED_MEDIA_TYPE",
            f"Unsupported image format: {format_name}. Allowed formats are JPEG, PNG, WebP, GIF.",
            status_code=415,
        )

    # 2. Open fresh image for processing (probe was invalidated by verify())
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            img = Image.open(io.BytesIO(raw_bytes))
            # Also ensure dimensions check even if headers were lazy
            w, h = img.size
            if w * h > MAX_IMAGE_PIXELS:
                raise Image.DecompressionBombError(f"Image {w}x{h} exceeds {MAX_IMAGE_PIXELS} pixels")
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise AppError(
            "IMAGE_TOO_LARGE",
            "Image dimensions exceed safety limit.",
            status_code=413,
        ) from None
    except (Image.UnidentifiedImageError, OSError, ValueError, SyntaxError):
        raise AppError(
            "UNSUPPORTED_MEDIA_TYPE",
            "Could not process image.",
            status_code=415,
        ) from None

    # For GIF: take the first frame
    if format_name == "GIF":
        try:
            img.seek(0)
        except (EOFError, OSError):
            logger.debug("GIF frame seek failed softly")

    # Handle EXIF orientation transposition
    try:
        img = ImageOps.exif_transpose(img)
    except (OSError, ValueError, SyntaxError):
        logger.debug("EXIF transposition skipped or unsupported")

    # Preserve alpha transparency for PNG/GIF/WebP, otherwise convert to RGB
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        img = img.convert("RGBA")
    else:
        img = img.convert("RGB")

    # 3. Resize: downscale only, never upscale
    max_dim = 1600 if purpose == "promotion" else 512
    if max(img.width, img.height) > max_dim:
        img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

    final_w, final_h = img.size

    # 4. Save to WebP without EXIF/GPS/ICC metadata
    out_buf = io.BytesIO()
    img.save(out_buf, format="WEBP", quality=80, method=6)
    webp_bytes = out_buf.getvalue()

    # 5. Generate secure destination path
    file_id = uuid.uuid4().hex
    category = "promotions" if purpose == "promotion" else "logos"
    relative_path = f"{category}/{file_id}.webp"

    # 6. Store in media storage
    await storage.put(relative_path, webp_bytes)

    public_url = f"{settings.media_public_base_url.rstrip('/')}/{relative_path}"

    # 7. Audit log (without file content)
    db.add(
        AuditLog(
            actor=admin.login,
            admin_user_id=admin.id,
            business_id=admin.business_id,
            action="media_uploaded",
            entity="media",
            before_state=None,
            after_state=safe_audit_snapshot(
                "media_uploaded",
                {
                    "purpose": purpose,
                    "bytes": len(webp_bytes),
                    "width": final_w,
                    "height": final_h,
                    "url": public_url,
                },
                admin_user_id=admin.id,
                business_id=admin.business_id,
            ),
        )
    )
    await db.commit()

    return ImageUploadResponse(
        url=public_url,
        width=final_w,
        height=final_h,
        bytes=len(webp_bytes),
    )
