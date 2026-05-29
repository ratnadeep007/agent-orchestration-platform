from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AgentBase(BaseModel):
    name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    system_prompt: str = Field(min_length=1)
    model: str = Field(min_length=1)
    tools: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)
    schedules: list[dict[str, Any]] = Field(default_factory=list)
    memory: dict[str, Any] = Field(default_factory=dict)
    skills: list[str] = Field(default_factory=list)
    interaction_rules: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


class AgentCreate(AgentBase):
    pass


class AgentUpdate(AgentBase):
    pass


class Agent(AgentBase):
    id: UUID
    sync_status: str
    openclaw_agent_id: str | None = None
    openclaw_workspace_path: str | None = None
    last_synced_at: str | None = None
    created_at: str
    updated_at: str


class AgentSyncResult(BaseModel):
    agent: Agent
    openclaw_agent_id: str
    openclaw_workspace_path: str
    local_workspace_path: str
    files: list[str]
