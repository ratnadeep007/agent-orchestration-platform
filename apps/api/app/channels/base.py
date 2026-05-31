from __future__ import annotations

from typing import Any, Protocol


class ChannelWebhookAdapter(Protocol):
    name: str

    def validate_webhook_secret(self, received_secret: str | None) -> None: ...

    def validate_allowed_chat(self, chat_id: str) -> None: ...

    def parse_inbound_update(self, update: dict[str, Any]) -> dict[str, Any] | None: ...
