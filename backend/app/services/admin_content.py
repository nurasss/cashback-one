"""Admin management of customer app content (promotions, broadcast notifications).

Superadmins manage global content (business_id NULL) and any business; business managers
manage only their own business. Every mutation is audited.
"""
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin_deps import AdminScope, scope_for_admin
from app.core.config import Settings
from app.core.errors import AppError
from app.models.admin import AdminUser
from app.models.entities import Business, Notification, Promotion
from app.schemas.admin import Page
from app.schemas.admin_content import (
    NotificationAdminItem,
    NotificationCreateRequest,
    PromotionAdminItem,
    PromotionCreateRequest,
    PromotionUpdateRequest,
)
from app.services.admin_mutations import _audit
from app.services.media_storage import MediaStorage, maybe_cleanup_old_media_file


def _not_found() -> AppError:
    return AppError("ADMIN_RESOURCE_NOT_FOUND", "Resource not found", 404)


def _owner_business(scope: AdminScope, requested: uuid.UUID | None) -> uuid.UUID | None:
    """Business the new content belongs to; managers are pinned to their own business."""
    if scope.business_id is not None:
        if requested is not None and requested != scope.business_id:
            raise _not_found()
        return scope.business_id
    scope.require_superadmin()
    return requested


def _can_access(scope: AdminScope, business_id: uuid.UUID | None) -> bool:
    return scope.business_id is None or business_id == scope.business_id


async def _require_business(db: AsyncSession, business_id: uuid.UUID | None) -> None:
    if business_id is not None and await db.scalar(
        select(Business.id).where(Business.id == business_id)
    ) is None:
        raise _not_found()


def _page(rows: list[Any], limit: int, offset: int, item: Any) -> Page[Any]:
    return Page(
        items=[item.model_validate(row) for row in rows[:limit]],
        limit=limit,
        offset=offset,
        has_more=len(rows) > limit,
    )


async def list_promotions(
    db: AsyncSession, scope: AdminScope, business_id: uuid.UUID | None, limit: int, offset: int
) -> Page[PromotionAdminItem]:
    stmt = select(Promotion)
    if scope.business_id is not None:
        stmt = stmt.where(Promotion.business_id == scope.business_id_for(business_id))
    elif business_id is not None:
        stmt = stmt.where(Promotion.business_id == business_id)
    rows = (
        await db.scalars(
            stmt.order_by(Promotion.sort_order.asc(), Promotion.created_at.desc(), Promotion.id)
            .limit(limit + 1)
            .offset(offset)
        )
    ).all()
    return _page(list(rows), limit, offset, PromotionAdminItem)


def _promotion_state(promo: Promotion) -> dict[str, Any]:
    return {
        "promotion_id": str(promo.id),
        "business_id": str(promo.business_id) if promo.business_id else None,
        "kind": promo.kind,
        "is_active": promo.is_active,
    }


async def create_promotion(
    db: AsyncSession, admin: AdminUser, body: PromotionCreateRequest
) -> PromotionAdminItem:
    scope = scope_for_admin(admin)
    business_id = _owner_business(scope, body.business_id)
    await _require_business(db, business_id)
    promo = Promotion(**body.model_dump(exclude={"business_id"}), business_id=business_id)
    db.add(promo)
    await db.flush()
    _audit(db, admin, business_id, "promotion_created", "promotion", None, _promotion_state(promo))
    await db.commit()
    await db.refresh(promo)
    return PromotionAdminItem.model_validate(promo)


async def _load_promotion(db: AsyncSession, scope: AdminScope, promotion_id: uuid.UUID) -> Promotion:
    promo = await db.scalar(select(Promotion).where(Promotion.id == promotion_id).with_for_update())
    if promo is None or not _can_access(scope, promo.business_id):
        raise _not_found()
    return promo


async def update_promotion(
    db: AsyncSession,
    admin: AdminUser,
    promotion_id: uuid.UUID,
    body: PromotionUpdateRequest,
    *,
    storage: MediaStorage | None = None,
    settings: Settings | None = None,
) -> PromotionAdminItem:
    promo = await _load_promotion(db, scope_for_admin(admin), promotion_id)
    before = _promotion_state(promo)
    old_image_url = promo.image_url
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(promo, field, value)
    if promo.starts_at and promo.ends_at and promo.ends_at <= promo.starts_at:
        raise AppError("VALIDATION_ERROR", "ends_at must be after starts_at", 422)
    await db.flush()
    _audit(db, admin, promo.business_id, "promotion_updated", "promotion", before, _promotion_state(promo))
    await db.commit()
    await db.refresh(promo)

    if storage is not None and settings is not None and old_image_url and old_image_url != promo.image_url:
        await maybe_cleanup_old_media_file(db, storage, old_image_url, settings)

    return PromotionAdminItem.model_validate(promo)


async def delete_promotion(
    db: AsyncSession,
    admin: AdminUser,
    promotion_id: uuid.UUID,
    *,
    storage: MediaStorage | None = None,
    settings: Settings | None = None,
) -> None:
    promo = await _load_promotion(db, scope_for_admin(admin), promotion_id)
    before = _promotion_state(promo)
    old_image_url = promo.image_url
    await db.delete(promo)
    _audit(db, admin, promo.business_id, "promotion_deleted", "promotion", before, None)
    await db.commit()

    if storage is not None and settings is not None and old_image_url:
        await maybe_cleanup_old_media_file(db, storage, old_image_url, settings)


async def list_notifications(
    db: AsyncSession, scope: AdminScope, business_id: uuid.UUID | None, limit: int, offset: int
) -> Page[NotificationAdminItem]:
    # Admins see broadcasts only; per-customer transaction notices stay private.
    stmt = select(Notification).where(Notification.user_id.is_(None))
    if scope.business_id is not None:
        stmt = stmt.where(Notification.business_id == scope.business_id_for(business_id))
    elif business_id is not None:
        stmt = stmt.where(Notification.business_id == business_id)
    rows = (
        await db.scalars(
            stmt.order_by(Notification.created_at.desc(), Notification.id.desc())
            .limit(limit + 1)
            .offset(offset)
        )
    ).all()
    return _page(list(rows), limit, offset, NotificationAdminItem)


def _notification_state(note: Notification) -> dict[str, Any]:
    return {
        "notification_id": str(note.id),
        "business_id": str(note.business_id) if note.business_id else None,
        "kind": note.kind,
        "targeted_user": note.user_id is not None,
    }


async def create_notification(
    db: AsyncSession, admin: AdminUser, body: NotificationCreateRequest
) -> NotificationAdminItem:
    scope = scope_for_admin(admin)
    business_id = _owner_business(scope, body.business_id)
    await _require_business(db, business_id)
    note = Notification(business_id=business_id, kind="info", title=body.title, body=body.body)
    db.add(note)
    await db.flush()
    _audit(db, admin, business_id, "notification_created", "notification", None, _notification_state(note))
    await db.commit()
    await db.refresh(note)
    return NotificationAdminItem.model_validate(note)


async def delete_notification(db: AsyncSession, admin: AdminUser, notification_id: uuid.UUID) -> None:
    scope = scope_for_admin(admin)
    note = await db.scalar(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id.is_(None)
        )
    )
    if note is None or not _can_access(scope, note.business_id):
        raise _not_found()
    before = _notification_state(note)
    await db.delete(note)
    _audit(db, admin, note.business_id, "notification_deleted", "notification", before, None)
    await db.commit()
