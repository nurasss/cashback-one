import hmac
import json
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.db.session import get_session
from app.schemas.wappi import WappiWebhookResponse
from app.services.wappi_webhook import process_wappi_webhook

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post(
    "/wappi",
    response_model=WappiWebhookResponse,
    status_code=200,
)
async def handle_wappi_webhook(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WappiWebhookResponse:
    """Incoming webhook handler for Wappi WhatsApp events."""
    # 1. Authenticate webhook request using configured header and secret
    auth_header_name = settings.wappi_webhook_auth_header
    provided_secret = request.headers.get(auth_header_name)
    expected_secret = settings.wappi_webhook_auth_secret

    if not provided_secret or not hmac.compare_digest(provided_secret, expected_secret):
        raise AppError(
            code="INVALID_WEBHOOK_AUTH",
            message="Invalid or missing webhook authentication secret",
            status_code=401,
        )

    # 2. Guard against oversized payloads
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > settings.wappi_webhook_max_body_bytes:
                raise AppError(
                    code="PAYLOAD_TOO_LARGE",
                    message=f"Payload exceeds limit of {settings.wappi_webhook_max_body_bytes} bytes",
                    status_code=413,
                )
        except ValueError:
            pass

    body_bytes = await request.body()
    if len(body_bytes) > settings.wappi_webhook_max_body_bytes:
        raise AppError(
            code="PAYLOAD_TOO_LARGE",
            message=f"Payload exceeds limit of {settings.wappi_webhook_max_body_bytes} bytes",
            status_code=413,
        )

    # 3. Parse JSON
    try:
        payload_data = json.loads(body_bytes.decode("utf-8"))
    except Exception as exc:
        raise AppError(
            code="INVALID_JSON_PAYLOAD",
            message="Request body must be valid JSON",
            status_code=400,
        ) from exc

    # 4. Delegate to webhook processing service
    return await process_wappi_webhook(session, payload_data)
