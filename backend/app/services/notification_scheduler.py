"""Background worker for scheduled in-app and push notifications."""
import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.time import utcnow
from app.models.entities import Notification
from app.services.push_sender import PushSender, get_push_sender
from app.services.push_service import send_broadcast_push

logger = logging.getLogger(__name__)


async def process_one_scheduled_notification(
    session: AsyncSession, sender: PushSender | None = None
) -> bool:
    """Find and send one pending scheduled broadcast notification using FOR UPDATE SKIP LOCKED.

    Returns True if a notification was processed, False if no pending notifications were found.
    """
    now = utcnow()
    stmt = (
        select(Notification)
        .where(
            Notification.user_id.is_(None),
            Notification.scheduled_at.is_not(None),
            Notification.scheduled_at <= now,
            Notification.push_sent_at.is_(None),
        )
        .order_by(Notification.scheduled_at.asc(), Notification.id.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    note = await session.scalar(stmt)
    if note is None:
        return False

    if sender is None:
        sender = get_push_sender()

    note.push_sent_at = now
    await session.flush()

    try:
        await send_broadcast_push(
            session=session,
            sender=sender,
            notification_id=note.id,
            title=note.title,
            body=note.body,
            business_id=note.business_id,
            send_push=True,
        )
    except Exception:
        logger.exception(
            "Scheduled broadcast push delivery failed for notification %s", note.id
        )

    await session.commit()
    return True


async def process_scheduled_notifications(
    session: AsyncSession, sender: PushSender | None = None, max_count: int = 50
) -> int:
    """Process pending scheduled notifications up to max_count.

    Returns the number of notifications sent.
    """
    processed = 0
    for _ in range(max_count):
        done = await process_one_scheduled_notification(session, sender)
        if not done:
            break
        processed += 1
    return processed


async def run_scheduled_notifications_loop(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    sender: PushSender | None = None,
    interval_seconds: float = 30.0,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Background task loop that periodically runs process_scheduled_notifications."""
    if session_factory is None:
        from app.db.session import async_session_maker

        session_factory = async_session_maker

    logger.info("Starting scheduled notifications worker (interval=%ss)", interval_seconds)
    while True:
        if stop_event is not None and stop_event.is_set():
            break
        try:
            async with session_factory() as session:
                count = await process_scheduled_notifications(session, sender=sender)
                if count > 0:
                    logger.info("Processed %d scheduled notification(s)", count)
        except asyncio.CancelledError:
            logger.info("Scheduled notifications worker cancelled")
            break
        except Exception:
            logger.exception("Unexpected error in scheduled notifications worker")

        try:
            if stop_event is not None:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
                    break
                except TimeoutError:
                    pass
            else:
                await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            logger.info("Scheduled notifications worker sleep cancelled")
            break
