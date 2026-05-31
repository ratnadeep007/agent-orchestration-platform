from __future__ import annotations

from typing import Any, Protocol


class ChannelDeliveryAdapter(Protocol):
    name: str

    def deliver(self, message: dict[str, Any]) -> dict[str, Any]: ...
