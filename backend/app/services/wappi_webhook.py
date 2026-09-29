import logging
import re
import uuid
from typing import Any

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.core.phone import normalize_phone
from app.core.security import CHALLENGE_CODE_ALPHABET, CHALLENGE_CODE_LENGTH
from app.core.time import utcnow
from app.models.entities import WappiWebhookEvent
from app.schemas.wappi import (
    WappiMessageItem,
    WappiWebhookPayload,
    WappiWebhookResponse,
)
from app.services.auth_confirmation import (
    confirm_login_challenge,
)

logger = logging.getLogger(__name__)

SENDER_JID_REGEX = re.compile(r"^(\d{10,15})@c\.us$")


async def process_wappi_webhook(
    session: AsyncSession,
    payload_data: WappiWebhookPayload | dict[str, Any],
) -> WappiWebhookResponse:
    """Process incoming Wappi webhook messages.

    Guarantees:
    - Profile isolation: only messages matching settings.wappi_login_profile_id are processed.
    - Idempotency: duplicate (profile_id, message_id) events are safely recognized with zero IntegrityErrors.
    - Atomicity: challenge confirmation and webhook event status are committed together in one transaction.
    - Crash/retry safety: operational/database failures trigger immediate rollback, leaving the message
      unreserved so that provider retries can be processed successfully without durable error markers.
    - Error hygiene: database and unexpected errors return controlled 503 errors without leaking SQL/traces.
    """
    if isinstance(payload_data, dict):
        payload = WappiWebhookPayload.model_validate(payload_data)
    else:
        payload = payload_data

    # Extract messages from payload
    if payload.messages is not None:
        items = payload.messages
    elif payload.id or payload.wh_type:
        items = [WappiMessageItem.model_validate(payload.model_dump())]
    else:
        items = []

    response = WappiWebhookResponse(status="ok")

    if not items:
        response.details.append({"reason": "empty_payload"})
        return response

    is_postgres = (
        session.get_bind().dialect.name == "postgresql"
        if session.get_bind()
        else False
    )
    dialect_insert = pg_insert if is_postgres else sqlite_insert

    for item in items:
        message_id = (item.id or "").strip()
        if not message_id:
            response.ignored += 1
            response.details.append({"reason": "missing_message_id"})
            continue

        item_profile_id = (
            item.profile_id or payload.profile_id or ""
        ).strip()
        if item_profile_id != settings.wappi_login_profile_id:
            response.ignored += 1
            response.details.append({
                "message_id": message_id,
                "reason": "ignored_profile",
                "profile_id": item_profile_id,
            })
            continue

        wh_type = (item.wh_type or payload.wh_type or "").strip()

        try:
            # 1. Idempotency reservation via ON CONFLICT DO NOTHING
            event_id = uuid.uuid4()
            stmt = (
                dialect_insert(WappiWebhookEvent)
                .values(
                    id=event_id,
                    profile_id=item_profile_id,
                    message_id=message_id,
                    wh_type=wh_type or "unknown",
                    result="processing",
                    received_at=utcnow(),
                )
                .on_conflict_do_nothing(
                    index_elements=["profile_id", "message_id"]
                )
                .returning(WappiWebhookEvent.id)
            )
            insert_res = await session.execute(stmt)
            inserted_id = insert_res.scalar_one_or_none()

            if inserted_id is None:
                # Duplicate message ID detected
                response.duplicates += 1
                response.details.append({
                    "message_id": message_id,
                    "result": "duplicate",
                })
                continue

            # 2. Filter: event type must be incoming_message
            if wh_type != "incoming_message":
                await session.execute(
                    update(WappiWebhookEvent)
                    .where(WappiWebhookEvent.id == inserted_id)
                    .values(result="ignored_event_type")
                )
                await session.commit()
                response.ignored += 1
                response.details.append({
                    "message_id": message_id,
                    "reason": "ignored_event_type",
                    "wh_type": wh_type,
                })
                continue

            # 3. Filter: message type must be chat
            msg_type = (item.type or "").strip()
            if msg_type != "chat":
                await session.execute(
                    update(WappiWebhookEvent)
                    .where(WappiWebhookEvent.id == inserted_id)
                    .values(result="ignored_non_chat_type")
                )
                await session.commit()
                response.ignored += 1
                response.details.append({
                    "message_id": message_id,
                    "reason": "ignored_non_chat_type",
                    "type": msg_type,
                })
                continue

            # 4. Filter: group chats (chat_type != dialog or JIDs ending with @g.us)
            chat_type = (item.chat_type or "").strip()
            from_jid = (item.from_ or "").strip()
            chat_id = (item.chat_id or "").strip()

            if (
                (chat_type and chat_type != "dialog")
                or from_jid.endswith("@g.us")
                or chat_id.endswith("@g.us")
            ):
                await session.execute(
                    update(WappiWebhookEvent)
                    .where(WappiWebhookEvent.id == inserted_id)
                    .values(result="ignored_group")
                )
                await session.commit()
                response.ignored += 1
                response.details.append({
                    "message_id": message_id,
                    "reason": "ignored_group",
                })
                continue

            # 5. Filter: direct sender JID validation
            sender_match = SENDER_JID_REGEX.match(from_jid or chat_id)
            if not sender_match:
                await session.execute(
                    update(WappiWebhookEvent)
                    .where(WappiWebhookEvent.id == inserted_id)
                    .values(result="invalid_sender")
                )
                await session.commit()
                response.ignored += 1
                response.details.append({
                    "message_id": message_id,
                    "reason": "invalid_sender",
                })
                continue

            sender_digits = sender_match.group(1)
            sender_phone = normalize_phone("+" + sender_digits)
            if not sender_phone:
                await session.execute(
                    update(WappiWebhookEvent)
                    .where(WappiWebhookEvent.id == inserted_id)
                    .values(result="invalid_sender_phone")
                )
                await session.commit()
                response.ignored += 1
                response.details.append({
                    "message_id": message_id,
                    "reason": "invalid_sender_phone",
                })
                continue

            # 6. Filter: challenge code format validation
            code = (item.body or "").strip().upper()
            if (
                len(code) != CHALLENGE_CODE_LENGTH
                or any(c not in CHALLENGE_CODE_ALPHABET for c in code)
            ):
                await session.execute(
                    update(WappiWebhookEvent)
                    .where(WappiWebhookEvent.id == inserted_id)
                    .values(result="invalid_code_format")
                )
                await session.commit()
                response.ignored += 1
                response.details.append({
                    "message_id": message_id,
                    "reason": "invalid_code_format",
                })
                continue

            # 7. Valid payload: invoke domain confirmation service
            confirm_res = await confirm_login_challenge(
                session=session,
                code=code,
                sender_phone=sender_phone,
                commit=False,
            )
            final_status = confirm_res.status.value
            await session.execute(
                update(WappiWebhookEvent)
                .where(WappiWebhookEvent.id == inserted_id)
                .values(result=final_status)
            )
            await session.commit()
            response.processed += 1
            response.details.append({
                "message_id": message_id,
                "result": final_status,
                "is_success": confirm_res.is_success,
                "challenge_id": (
                    str(confirm_res.challenge_id)
                    if confirm_res.challenge_id
                    else None
                ),
            })
        except (SQLAlchemyError, OSError, TimeoutError, ConnectionError) as exc:
            logger.exception(
                "Operational database failure processing Wappi message %s (type=%s)",
                message_id,
                wh_type,
            )
            await session.rollback()
            raise AppError(
                code="WEBHOOK_PROCESSING_UNAVAILABLE",
                message="Webhook could not be processed. Retry later.",
                status_code=503,
            ) from exc
        except AppError:
            await session.rollback()
            raise
        except Exception as exc:
            logger.exception(
                "Unexpected failure processing Wappi message %s (type=%s)",
                message_id,
                wh_type,
            )
            await session.rollback()
            raise AppError(
                code="WEBHOOK_PROCESSING_UNAVAILABLE",
                message="Webhook could not be processed. Retry later.",
                status_code=503,
            ) from exc

    return response
