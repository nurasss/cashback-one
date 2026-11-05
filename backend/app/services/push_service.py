"""Push notification service for user devices."""
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.time import utcnow
from app.models.entities import Business, Device
from app.services.push_sender import PushSender, PushStatus

logger = logging.getLogger(__name__)


async def resolve_allowed_app_ids(
    session: AsyncSession, business_id: uuid.UUID | None
) -> set[str] | None:
    """Resolve allowed device app_ids for an event of the given business.

    - If business_id is None: returns None (no app_id filter, sends to all active devices).
    - If business_id is provided and business has android_app_id:
        {business.android_app_id, settings.push_shared_app_id}.
    - If business_id is provided and business has no android_app_id (or not found):
        {settings.push_shared_app_id}.
    """
    if business_id is None:
        return None
    shared_id = settings.push_shared_app_id
    business_app_id = await session.scalar(
        select(Business.android_app_id).where(Business.id == business_id)
    )
    if business_app_id:
        return {business_app_id, shared_id}
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
