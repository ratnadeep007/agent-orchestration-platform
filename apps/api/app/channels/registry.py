from __future__ import annotations

from app.channels.telegram import TelegramWebhookAdapter


def get_channel_adapter(channel: str):
    normalized = channel.strip().lower()
    if normalized == "telegram":
        return TelegramWebhookAdapter()
    raise RuntimeError(f"Unsupported inbound channel: {channel}")
