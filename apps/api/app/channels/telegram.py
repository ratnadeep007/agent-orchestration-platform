from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from app.config import settings


class TelegramWebhookAdapter:
    name = "telegram"

    def validate_webhook_secret(self, received_secret: str | None) -> None:
        if settings.telegram_webhook_secret and received_secret != settings.telegram_webhook_secret:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Telegram webhook secret",
            )

    def validate_allowed_chat(self, chat_id: str) -> None:
        if settings.telegram_allowed_chat_id and chat_id != settings.telegram_allowed_chat_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Telegram chat is not allowed",
            )

    def parse_inbound_update(self, update: dict[str, Any]) -> dict[str, Any] | None:
        message = update.get("message") or update.get("edited_message")
        if not isinstance(message, dict):
            return None

        chat = message.get("chat")
        if not isinstance(chat, dict) or chat.get("id") is None:
            return None

        text = str(message.get("text") or message.get("caption") or "")
        if not text:
            return None

        chat_id = str(chat["id"])
        telegram_message_id = message.get("message_id")
        external_id = (
            f"telegram:{chat_id}:{telegram_message_id}"
            if telegram_message_id is not None
            else f"telegram:{chat_id}:{update.get('update_id', 'unknown')}"
        )
        return {
            "chat_id": chat_id,
            "text": text,
            "external_id": external_id,
            "telegram_message_id": telegram_message_id,
            "from": message.get("from", {}),
        }


def get_telegram_webhook_adapter() -> TelegramWebhookAdapter:
    return TelegramWebhookAdapter()
