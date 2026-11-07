"""Push notification service for user devices."""
import asyncio
import logging
import uuid
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.time import utcnow
from app.models.entities import Business, Card, Device, UserCard
from app.schemas.admin_content import BroadcastPushResult
from app.services.push_sender import PushResult, PushSender, PushStatus

logger = logging.getLogger(__name__)


async def resolve_allowed_app_ids(
    session: AsyncSession, business_id: uuid.UUID | None
) -> set[str] | None:
    """Resolve allowed device app_ids for an event of the given business.

    Owner decision (2026-11-07):
    - If business_id is None: returns None (no app_id filter, sends to all active devices).
    - If business has its own application (android_app_id is set):
        {business.android_app_id} ONLY (general Cashback One app does NOT receive push).
    - If business has no android_app_id (or not found):
        {settings.push_shared_app_id} (shared Cashback One app).
    """
    if business_id is None:
        return None
    shared_id = settings.push_shared_app_id
    business_app_id = await session.scalar(
        select(Business.android_app_id).where(Business.id == business_id)
    )
    if business_app_id:
        return {business_app_id}
    return {shared_id}


async def has_active_device(
    session: AsyncSession,
    user_id: uuid.UUID,
    business_id: uuid.UUID | None = None,
    allowed_app_ids: set[str] | list[str] | None = None,
) -> bool:
    """Check if the user has at least one active push device matching allowed apps."""
    if allowed_app_ids is None and business_id is not None:
        allowed = await resolve_allowed_app_ids(session, business_id)
    elif allowed_app_ids is not None:
        allowed = set(allowed_app_ids)
    else:
        allowed = None

    stmt = select(Device.id).where(
        Device.user_id == user_id,
        Device.disabled_at.is_(None),
    )
    if allowed is not None:
        stmt = stmt.where(Device.app_id.in_(allowed))
    stmt = stmt.limit(1)
    res = await session.scalar(stmt)
    return res is not None


async def send_to_user(
    session: AsyncSession,
    sender: PushSender,
    user_id: uuid.UUID,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
    business_id: uuid.UUID | None = None,
    allowed_app_ids: set[str] | list[str] | None = None,
) -> int:
    """Send a push notification to active devices of a user matching allowed apps.

    Returns the number of messages accepted by FCM.
    Invalid tokens (UNREGISTERED, INVALID_ARGUMENT) are marked as disabled_at.
    Temporary errors leave device records active.
    """
    if allowed_app_ids is None and business_id is not None:
        allowed = await resolve_allowed_app_ids(session, business_id)
    elif allowed_app_ids is not None:
        allowed = set(allowed_app_ids)
    else:
        allowed = None

    stmt = select(Device).where(
        Device.user_id == user_id,
        Device.disabled_at.is_(None),
    )
    if allowed is not None:
        stmt = stmt.where(Device.app_id.in_(allowed))
    devices = (await session.scalars(stmt)).all()
    if not devices:
        return 0

    delivered_count = 0
    now = utcnow()
    has_mutations = False

    for device in devices:
        result = await sender.send(
            token=device.push_token,
            title=title,
            body=body,
            data=data,
        )
        if result.status == PushStatus.DELIVERED:
            delivered_count += 1
        elif result.status == PushStatus.INVALID_TOKEN:
            device.disabled_at = now
            has_mutations = True
            logger.info(
                "Device push token marked disabled: reason=%s device_id=%s",
                result.error_details,
                device.id,
            )
        elif result.status in (PushStatus.TEMPORARY_ERROR, PushStatus.REJECTED):
            logger.warning(
                "Push delivery failure (device kept active): status=%s reason=%s device_id=%s",
                result.status.value,
                result.error_details,
                device.id,
            )

    if has_mutations:
        await session.commit()

    return delivered_count


async def get_broadcast_target_devices(
    session: AsyncSession, business_id: uuid.UUID | None
) -> list[Device]:
    """Resolve active target devices for a broadcast notification.

    Owner decision (2026-11-07):
    - business_id is None ('Все бизнесы'): all active devices (disabled_at IS NULL).
    - business_id is set (Business B):
        - if B is inactive or not found: returns empty list.
        - if B has android_app_id: devices with app_id == B.android_app_id ONLY
          (devices of shared app do NOT receive push).
        - if B does NOT have android_app_id: devices with app_id == push_shared_app_id
          whose user has a visible card of B (hidden_at IS NULL).
    Deduplicates devices by push_token so each device receives at most 1 message.
    """
    if business_id is None:
        stmt = select(Device).where(Device.disabled_at.is_(None))
    else:
        biz = await session.get(Business, business_id)
        if biz is None or biz.status != "active":
            return []

        if biz.android_app_id:
            stmt = select(Device).where(
                Device.disabled_at.is_(None),
                Device.app_id == biz.android_app_id,
            )
        else:
            shared_app_id = settings.push_shared_app_id
            user_has_visible_card = (
                select(UserCard.user_id)
                .join(Card, Card.id == UserCard.card_id)
                .where(
                    Card.business_id == business_id,
                    UserCard.hidden_at.is_(None),
                )
            )
            stmt = select(Device).where(
                Device.disabled_at.is_(None),
                Device.app_id == shared_app_id,
                Device.user_id.in_(user_has_visible_card),
            )

    raw_devices = (await session.scalars(stmt)).all()
    seen_tokens: set[str] = set()
    devices: list[Device] = []
    for d in raw_devices:
        if d.push_token not in seen_tokens:
            seen_tokens.add(d.push_token)
            devices.append(d)
    return devices


async def send_broadcast_push(
    session: AsyncSession,
    sender: PushSender,
    notification_id: uuid.UUID,
    title: str,
    body: str,
    business_id: uuid.UUID | None = None,
    send_push: bool = True,
) -> BroadcastPushResult:
    """Deliver a broadcast notification via push to active candidate devices.

    Never raises: any push error is handled, device states updated on invalid tokens,
    and returns BroadcastPushResult with status ('sent', 'disabled', 'skipped', 'failed').
    """
    if not send_push:
        return BroadcastPushResult(status="skipped", devices=0, delivered=0)

    if getattr(sender, "disabled", False):
        return BroadcastPushResult(status="disabled", devices=0, delivered=0)

    devices = await get_broadcast_target_devices(session, business_id)
    total_devices = len(devices)
    if total_devices == 0:
        return BroadcastPushResult(status="skipped", devices=0, delivered=0)

    data = {"type": "broadcast", "notification_id": str(notification_id)}
    sem = asyncio.Semaphore(10)
    now = utcnow()
    delivered_count = 0
    has_mutations = False

    async def _send_one(device: Device) -> tuple[Device, PushResult]:
        async with sem:
            res = await sender.send(
                token=device.push_token,
                title=title,
                body=body,
                data=data,
            )
            return device, res

    try:
        raw_results = await asyncio.wait_for(
            asyncio.gather(*[_send_one(d) for d in devices], return_exceptions=True),
            timeout=30.0,
        )
    except TimeoutError:
        logger.warning("Broadcast push timed out during dispatch")
        return BroadcastPushResult(status="failed", devices=total_devices, delivered=0)
    except Exception:
        logger.exception("Broadcast push failed during dispatch")
        return BroadcastPushResult(status="failed", devices=total_devices, delivered=0)

    for item in raw_results:
        if isinstance(item, BaseException):
            logger.warning("Push send exception during dispatch: %s", item)
            continue
        device, res = item
        if res.status == PushStatus.DELIVERED:
            delivered_count += 1
        elif res.status == PushStatus.INVALID_TOKEN:
            device.disabled_at = now
            has_mutations = True
            logger.info(
                "Device push token marked disabled: reason=%s device_id=%s",
                res.error_details,
                device.id,
            )
        elif res.status in (PushStatus.TEMPORARY_ERROR, PushStatus.REJECTED):
            logger.warning(
                "Push delivery failure (device kept active): status=%s reason=%s device_id=%s",
                res.status.value,
                res.error_details,
                device.id,
            )

    if has_mutations:
        try:
            await session.commit()
        except Exception:
            logger.exception("Failed to commit disabled_at for invalid push tokens")

    if delivered_count > 0:
        status: Literal["sent", "disabled", "skipped", "failed"] = "sent"
    else:
        status = "failed"

    return BroadcastPushResult(
        status=status,
        devices=total_devices,
        delivered=delivered_count,
    )
