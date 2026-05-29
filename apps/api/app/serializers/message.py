from typing import Any

from app.models.message import Message


def serialize_message(row: dict[str, Any]) -> Message:
    payload = dict(row)
    payload["created_at"] = payload["created_at"].isoformat()
    return Message.model_validate(payload)
