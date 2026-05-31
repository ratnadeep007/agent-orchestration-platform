from __future__ import annotations

from typing import Any

from app.channels.telegram import TelegramDeliveryAdapter


def deliver_message(message: dict[str, Any]) -> dict[str, Any]:
    channel = str(message.get("channel") or "").strip().lower()
    if channel == "telegram":
        return TelegramDeliveryAdapter().deliver(message)
    return {"skipped": True, "reason": f"unsupported channel: {channel or 'unknown'}"}
