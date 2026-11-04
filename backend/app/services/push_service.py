"""Push notification service for user devices."""
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.models.entities import Device
from app.services.push_sender import PushSender, PushStatus

logger = logging.getLogger(__name__)


async def has_active_device(session: AsyncSession, user_id: uuid.UUID) -> bool:
    """Check if the user has at least one active push device."""
    stmt = (
        select(Device.id)
        .where(Device.user_id == user_id, Device.disabled_at.is_(None))
        .limit(1)
    )
    res = await session.scalar(stmt)
    return res is not None


async def send_to_user(
    session: AsyncSession,
    sender: PushSender,
    user_id: uuid.UUID,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> int:
    """Send a push notification to all active devices of a user.

    Returns the number of messages accepted by FCM.
    Invalid tokens (UNREGISTERED, INVALID_ARGUMENT) are marked as disabled_at.
    Temporary errors leave device records active.
    """
    stmt = select(Device).where(
        Device.user_id == user_id,
        Device.disabled_at.is_(None),
    )
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
