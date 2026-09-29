from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WappiMessageItem(BaseModel):
    """Individual message event object from Wappi webhook payload."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    wh_type: str | None = None
    profile_id: str | None = None
    id: str | None = None
    body: str | None = None
    type: str | None = None
    from_: str | None = Field(default=None, alias="from")
    to: str | None = None
    chat_id: str | None = Field(default=None, alias="chatId")
    chat_type: str | None = None
    sender_name: str | None = Field(default=None, alias="senderName")
    time: int | None = None
    timestamp: int | str | None = None


class WappiWebhookPayload(BaseModel):
    """Container payload for Wappi webhook request."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    messages: list[WappiMessageItem] | None = None
    profile_id: str | None = None
    wh_type: str | None = None
    id: str | None = None
    body: str | None = None
    type: str | None = None
    from_: str | None = Field(default=None, alias="from")
    to: str | None = None
    chat_id: str | None = Field(default=None, alias="chatId")
    chat_type: str | None = None


class WappiWebhookResponse(BaseModel):
    """Response returned to Wappi webhook provider."""

    status: str = "ok"
    processed: int = 0
    ignored: int = 0
    duplicates: int = 0
    details: list[dict[str, Any]] = Field(default_factory=list)
