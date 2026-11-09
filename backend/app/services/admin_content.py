"""Admin management of customer app content (promotions, broadcast notifications).

Superadmins manage global content (business_id NULL) and any business; business managers
manage only their own business. Every mutation is audited.
"""
import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin_deps import AdminScope, scope_for_admin
from app.core.config import Settings
from app.core.errors import AppError
from app.core.time import as_utc, utcnow
from app.models.admin import AdminUser
from app.models.entities import Business, BusinessStore, Notification, Promotion
from app.schemas.admin import Page
from app.schemas.admin_content import (
    AppTextsResponse,
    AppTextsUpdateRequest,
    BroadcastPushResult,
    BusinessSplashConfigResponse,
    BusinessSplashConfigUpdateRequest,
    BusinessStoreAdminItem,
    BusinessStoreCreateRequest,
    BusinessStoreUpdateRequest,
    LocalizedAppText,
    NotificationAdminItem,
    NotificationCreateRequest,
    PromotionAdminItem,
    PromotionCreateRequest,
    PromotionUpdateRequest,
)
from app.services.admin_mutations import _audit
from app.services.media_storage import MediaStorage, maybe_cleanup_old_media_file
from app.services.push_sender import PushSender, get_push_sender
from app.services.push_service import send_broadcast_push

logger = logging.getLogger(__name__)


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
    db: AsyncSession,
    scope: AdminScope,
    business_id: uuid.UUID | None,
    limit: int,
    offset: int,
    *,
    kind: str | None = None,
) -> Page[PromotionAdminItem]:
    stmt = select(Promotion)
    if scope.business_id is not None:
        stmt = stmt.where(Promotion.business_id == scope.business_id_for(business_id))
    elif business_id is not None:
        stmt = stmt.where(Promotion.business_id == business_id)
    if kind is not None:
        stmt = stmt.where(Promotion.kind == kind)
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
    if "starts_at" in body.model_fields_set and body.starts_at is not None:
        if promo.starts_at is None or as_utc(promo.starts_at) != as_utc(body.starts_at):
            val_utc = as_utc(body.starts_at)
            if val_utc < utcnow() - timedelta(minutes=5):
                raise AppError("VALIDATION_ERROR", "starts_at cannot be in the past", 422)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(promo, field, value)
    if promo.starts_at and promo.ends_at and as_utc(promo.ends_at) <= as_utc(promo.starts_at):
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


def _notification_state(
    note: Notification,
    push_devices: int | None = None,
    push_delivered: int | None = None,
) -> dict[str, Any]:
    state: dict[str, Any] = {
        "notification_id": str(note.id),
        "business_id": str(note.business_id) if note.business_id else None,
        "kind": note.kind,
        "targeted_user": note.user_id is not None,
        "scheduled_at": note.scheduled_at.isoformat() if note.scheduled_at else None,
        "push_sent_at": note.push_sent_at.isoformat() if note.push_sent_at else None,
    }
    if push_devices is not None:
        state["push_devices"] = push_devices
    if push_delivered is not None:
        state["push_delivered"] = push_delivered
    return state


async def create_notification(
    db: AsyncSession,
    admin: AdminUser,
    body: NotificationCreateRequest,
    sender: PushSender | None = None,
) -> NotificationAdminItem:
    scope = scope_for_admin(admin)
    business_id = _owner_business(scope, body.business_id)
    await _require_business(db, business_id)

    is_scheduled = body.scheduled_at is not None
    push_sent_at: datetime | None = None
    if not is_scheduled and body.send_push:
        push_sent_at = utcnow()
    elif is_scheduled and not body.send_push:
        # If user explicitly turned off push for a scheduled notice, mark push as skipped
        push_sent_at = body.scheduled_at

    note = Notification(
        business_id=business_id,
        kind="info",
        title=body.title,
        body=body.body,
        scheduled_at=body.scheduled_at,
        push_sent_at=push_sent_at,
    )
    db.add(note)
    await db.flush()
    await db.commit()
    await db.refresh(note)

    push_res: BroadcastPushResult | None = None
    if not is_scheduled:
        if sender is None:
            sender = get_push_sender()

        try:
            push_res = await send_broadcast_push(
                session=db,
                sender=sender,
                notification_id=note.id,
                title=note.title,
                body=note.body,
                business_id=business_id,
                send_push=body.send_push,
            )
        except Exception:
            logger.exception("Broadcast push unhandled failure")
            push_res = BroadcastPushResult(status="failed", devices=0, delivered=0)

    try:
        _audit(
            db,
            admin,
            business_id,
            "notification_created",
            "notification",
            None,
            _notification_state(
                note,
                push_devices=push_res.devices if push_res else None,
                push_delivered=push_res.delivered if push_res else None,
            ),
        )
        await db.commit()
    except Exception:
        logger.exception("Failed to write audit log for notification")

    return NotificationAdminItem(
        id=note.id,
        business_id=note.business_id,
        user_id=note.user_id,
        kind=note.kind,
        title=note.title,
        body=note.body,
        created_at=note.created_at,
        scheduled_at=note.scheduled_at,
        push_sent_at=note.push_sent_at,
        push=push_res,
    )


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


def _store_state(store: BusinessStore) -> dict[str, Any]:
    return {
        "store_id": str(store.id),
        "business_id": str(store.business_id),
        "title_ru": store.title_ru,
        "title_kk": store.title_kk,
        "address_ru": store.address_ru,
        "address_kk": store.address_kk,
        "map_url": store.map_url,
        "sort_order": store.sort_order,
        "is_active": store.is_active,
    }


def _check_business_scope(scope: AdminScope, business_id: uuid.UUID) -> None:
    if scope.business_id is not None and scope.business_id != business_id:
        raise _not_found()


async def list_stores(
    db: AsyncSession, admin: AdminUser, business_id: uuid.UUID
) -> list[BusinessStoreAdminItem]:
    scope = scope_for_admin(admin)
    _check_business_scope(scope, business_id)
    await _require_business(db, business_id)
    stmt = (
        select(BusinessStore)
        .where(BusinessStore.business_id == business_id)
        .order_by(
            BusinessStore.sort_order.asc(),
            BusinessStore.created_at.asc(),
            BusinessStore.id.asc(),
        )
    )
    rows = (await db.scalars(stmt)).all()
    return [BusinessStoreAdminItem.model_validate(row) for row in rows]


async def create_store(
    db: AsyncSession,
    admin: AdminUser,
    business_id: uuid.UUID,
    body: BusinessStoreCreateRequest,
) -> BusinessStoreAdminItem:
    scope = scope_for_admin(admin)
    _check_business_scope(scope, business_id)
    await _require_business(db, business_id)
    store = BusinessStore(business_id=business_id, **body.model_dump())
    db.add(store)
    await db.flush()
    _audit(db, admin, business_id, "store_created", "business_store", None, _store_state(store))
    await db.commit()
    await db.refresh(store)
    return BusinessStoreAdminItem.model_validate(store)


async def update_store(
    db: AsyncSession,
    admin: AdminUser,
    business_id: uuid.UUID,
    store_id: uuid.UUID,
    body: BusinessStoreUpdateRequest,
) -> BusinessStoreAdminItem:
    scope = scope_for_admin(admin)
    _check_business_scope(scope, business_id)
    await _require_business(db, business_id)
    store = await db.scalar(
        select(BusinessStore)
        .where(BusinessStore.id == store_id, BusinessStore.business_id == business_id)
        .with_for_update()
    )
    if store is None:
        raise _not_found()
    before = _store_state(store)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(store, field, value)
    await db.flush()
    _audit(db, admin, business_id, "store_updated", "business_store", before, _store_state(store))
    await db.commit()
    await db.refresh(store)
    return BusinessStoreAdminItem.model_validate(store)


async def delete_store(
    db: AsyncSession, admin: AdminUser, business_id: uuid.UUID, store_id: uuid.UUID
) -> None:
    scope = scope_for_admin(admin)
    _check_business_scope(scope, business_id)
    await _require_business(db, business_id)
    store = await db.scalar(
        select(BusinessStore)
        .where(BusinessStore.id == store_id, BusinessStore.business_id == business_id)
        .with_for_update()
    )
    if store is None:
        raise _not_found()
    before = _store_state(store)
    await db.delete(store)
    _audit(db, admin, business_id, "store_deleted", "business_store", before, None)
    await db.commit()


async def get_app_texts(
    db: AsyncSession, admin: AdminUser, business_id: uuid.UUID
) -> AppTextsResponse:
    scope = scope_for_admin(admin)
    _check_business_scope(scope, business_id)
    biz = await db.scalar(select(Business).where(Business.id == business_id))
    if biz is None:
        raise _not_found()
    raw = biz.app_texts or {}
    return AppTextsResponse(
        home_text=LocalizedAppText.model_validate(raw.get("home_text") or {}),
        home_store_note_lead=LocalizedAppText.model_validate(
            raw.get("home_store_note_lead") or {}
        ),
        balance_delay_note=LocalizedAppText.model_validate(
            raw.get("balance_delay_note") or {}
        ),
    )


async def update_app_texts(
    db: AsyncSession,
    admin: AdminUser,
    business_id: uuid.UUID,
    body: AppTextsUpdateRequest,
) -> AppTextsResponse:
    scope = scope_for_admin(admin)
    _check_business_scope(scope, business_id)
    biz = await db.scalar(
        select(Business).where(Business.id == business_id).with_for_update()
    )
    if biz is None:
        raise _not_found()
    before = biz.app_texts
    current_texts = dict(biz.app_texts or {})
    for key, val in body.model_dump(exclude_unset=True).items():
        current_texts[key] = val
    biz.app_texts = current_texts
    await db.flush()
    _audit(
        db,
        admin,
        business_id,
        "app_texts_updated",
        "business_app_texts",
        before,
        biz.app_texts,
    )
    await db.commit()
    await db.refresh(biz)
    raw = biz.app_texts or {}
    return AppTextsResponse(
        home_text=LocalizedAppText.model_validate(raw.get("home_text") or {}),
        home_store_note_lead=LocalizedAppText.model_validate(
            raw.get("home_store_note_lead") or {}
        ),
        balance_delay_note=LocalizedAppText.model_validate(
            raw.get("balance_delay_note") or {}
        ),
    )


async def get_splash_config(
    db: AsyncSession, admin: AdminUser, business_id: uuid.UUID
) -> BusinessSplashConfigResponse:
    scope = scope_for_admin(admin)
    _check_business_scope(scope, business_id)
    biz = await db.scalar(select(Business).where(Business.id == business_id))
    if biz is None:
        raise _not_found()
    raw = biz.splash_config or {}
    return BusinessSplashConfigResponse(
        business_id=biz.id,
        enabled=bool(raw.get("enabled", False)),
        media_type=raw.get("media_type"),
        media_url=raw.get("media_url"),
        width=raw.get("width"),
        height=raw.get("height"),
        duration_seconds=raw.get("duration_seconds"),
        file_size=raw.get("file_size"),
        version=raw.get("version"),
    )


async def update_splash_config(
    db: AsyncSession,
    admin: AdminUser,
    business_id: uuid.UUID,
    body: BusinessSplashConfigUpdateRequest,
    *,
    storage: MediaStorage,
    settings: Settings,
) -> BusinessSplashConfigResponse:
    scope = scope_for_admin(admin)
    _check_business_scope(scope, business_id)
    biz = await db.scalar(
        select(Business).where(Business.id == business_id).with_for_update()
    )
    if biz is None:
        raise _not_found()

    before = biz.splash_config
    old_url = (before or {}).get("media_url") if isinstance(before, dict) else None

    # Validate media URL if enabled
    if body.enabled:
        if not body.media_url:
            raise AppError("VALIDATION_ERROR", "media_url is required when enabled is true", 422)
        base = settings.media_public_base_url.rstrip("/") + "/"
        if not body.media_url.startswith(base):
            raise AppError("VALIDATION_ERROR", "media_url must point to the media storage host", 422)
        rel_path = body.media_url[len(base):]
        if not re.match(r"^splashes/[0-9a-f]{32}\.(webp|mp4)$", rel_path):
            raise AppError("VALIDATION_ERROR", "media_url must be a valid stored splash asset", 422)

    version_token = uuid.uuid4().hex[:16]
    new_config = {
        "enabled": body.enabled,
        "media_type": body.media_type,
        "media_url": body.media_url,
        "width": body.width,
        "height": body.height,
        "duration_seconds": body.duration_seconds,
        "file_size": body.file_size,
        "version": version_token,
    }

    biz.splash_config = new_config
    biz.updated_at = utcnow()
    await db.flush()

    _audit(
        db,
        admin,
        business_id,
        "business_splash_updated",
        "business_splash",
        before,
        new_config,
    )
    await db.commit()
    await db.refresh(biz)

    # If media changed and old_url is distinct, cleanup old file safely
    if old_url and old_url != body.media_url:
        await maybe_cleanup_old_media_file(
            db=db,
            storage=storage,
            old_url=old_url,
            settings=settings,
        )

    return BusinessSplashConfigResponse(
        business_id=biz.id,
        enabled=bool(new_config["enabled"]),
        media_type=new_config["media_type"],
        media_url=new_config["media_url"],
        width=new_config["width"],
        height=new_config["height"],
        duration_seconds=new_config["duration_seconds"],
        file_size=new_config["file_size"],
        version=new_config["version"],
    )
