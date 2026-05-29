from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class MessageCreate(BaseModel):
    run_id: UUID | None = None
    agent_id: UUID | None = None
    channel: str = Field(min_length=1)
    direction: str = Field(pattern="^(inbound|outbound|agent)$")
    body: str = Field(min_length=1)
    external_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RuntimeEventCreate(BaseModel):
    source: str = "openclaw"
    event_type: str = Field(min_length=1)
    channel: str = Field(min_length=1)
    direction: str = Field(pattern="^(inbound|outbound|agent)$")
    body: str = Field(min_length=1)
    run_id: UUID | None = None
    agent_id: UUID | None = None
    external_id: str | None = None
    delivery_state: str = "mirrored"
    metadata: dict[str, Any] = Field(default_factory=dict)


class Message(BaseModel):
    id: UUID
    run_id: UUID | None
    agent_id: UUID | None
    channel: str
    direction: str
    body: str
    delivery_state: str
    external_id: str | None
    metadata: dict[str, Any]
    created_at: str
