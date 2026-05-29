from typing import Any

from pydantic import BaseModel, Field

from app.models.message import Message


class TelegramWebhookResponse(BaseModel):
    accepted: bool
    message: Message | None = None


class TelegramSendRequest(BaseModel):
    chat_id: str = Field(min_length=1)
    body: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
