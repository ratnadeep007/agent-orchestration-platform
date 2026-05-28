from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from psycopg import Connection
from pydantic import BaseModel, Field

from app.config import settings
from app.db import get_connection
from app.messages import (
    Message,
    MessageBus,
    MessageRepository,
    RuntimeEventCreate,
    _serialize,
    get_message_bus,
)

router = APIRouter(prefix="/telegram", tags=["telegram"])


class TelegramWebhookResponse(BaseModel):
    accepted: bool
    message: Message | None = None


class TelegramSendRequest(BaseModel):
    chat_id: str = Field(min_length=1)
    body: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


def get_telegram_message_repository(
    connection: Connection = Depends(get_connection),
) -> MessageRepository:
    return MessageRepository(connection)


@router.post("/webhook", response_model=TelegramWebhookResponse)
def telegram_webhook(
    update: dict[str, Any],
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    repository: MessageRepository = Depends(get_telegram_message_repository),
) -> TelegramWebhookResponse:
    _validate_webhook_secret(x_telegram_bot_api_secret_token)

    message = update.get("message") or update.get("edited_message")
    if not isinstance(message, dict):
        return TelegramWebhookResponse(accepted=False)

    chat = message.get("chat")
    if not isinstance(chat, dict) or chat.get("id") is None:
        return TelegramWebhookResponse(accepted=False)

    chat_id = str(chat["id"])
    _validate_allowed_chat(chat_id)

    text = str(message.get("text") or message.get("caption") or "")
    if not text:
        return TelegramWebhookResponse(accepted=False)

    telegram_message_id = message.get("message_id")
    external_id = (
        f"telegram:{chat_id}:{telegram_message_id}"
        if telegram_message_id is not None
        else f"telegram:{chat_id}:{update.get('update_id', 'unknown')}"
    )
    row = repository.mirror_event(
        RuntimeEventCreate(
            source="telegram",
            event_type="telegram.message.received",
            channel="telegram",
            direction="inbound",
            body=text,
            external_id=external_id,
            metadata={
                "chat_id": chat_id,
                "update_id": update.get("update_id"),
                "message_id": telegram_message_id,
                "from": message.get("from", {}),
            },
        )
    )
    return TelegramWebhookResponse(accepted=True, message=_serialize(row))


@router.post("/messages", response_model=Message, status_code=status.HTTP_202_ACCEPTED)
def queue_telegram_message(
    payload: TelegramSendRequest,
    repository: MessageRepository = Depends(get_telegram_message_repository),
    bus: MessageBus = Depends(get_message_bus),
) -> Message:
    _validate_allowed_chat(payload.chat_id)
    row = repository.create_outbound(
        channel="telegram",
        body=payload.body,
        metadata={**payload.metadata, "chat_id": payload.chat_id},
    )
    bus.enqueue(row["id"])
    return _serialize(row)


def _validate_webhook_secret(received_secret: str | None) -> None:
    if settings.telegram_webhook_secret and received_secret != settings.telegram_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Telegram webhook secret",
        )


def _validate_allowed_chat(chat_id: str) -> None:
    if settings.telegram_allowed_chat_id and chat_id != settings.telegram_allowed_chat_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Telegram chat is not allowed",
        )
