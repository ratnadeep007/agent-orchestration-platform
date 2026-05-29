from typing import Any

from app.models.agent import Agent


def serialize_agent(row: dict[str, Any]) -> Agent:
    payload = dict(row)
    payload["created_at"] = payload["created_at"].isoformat()
    payload["updated_at"] = payload["updated_at"].isoformat()
    if payload.get("last_synced_at"):
        payload["last_synced_at"] = payload["last_synced_at"].isoformat()
    return Agent.model_validate(payload)
