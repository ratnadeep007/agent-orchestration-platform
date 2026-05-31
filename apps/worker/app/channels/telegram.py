from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import settings


class TelegramDeliveryAdapter:
    name = "telegram"

    def deliver(self, message: dict[str, Any]) -> dict[str, Any]:
        if not settings.telegram_bot_token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is required for outbound Telegram delivery")

        chat_id = str(message["metadata"].get("chat_id", ""))
        if not chat_id:
            raise RuntimeError("metadata.chat_id is required for outbound Telegram delivery")

        if settings.telegram_allowed_chat_id and chat_id != settings.telegram_allowed_chat_id:
            raise RuntimeError("Telegram chat is not allowed")

        payload = json.dumps({"chat_id": chat_id, "text": message["body"]}).encode("utf-8")
        request = Request(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as caught:
            body = caught.read().decode("utf-8")
            raise RuntimeError(f"Telegram send failed with HTTP {caught.code}: {body}") from caught
        except URLError as caught:
            raise RuntimeError(f"Telegram send failed: {caught.reason}") from caught
