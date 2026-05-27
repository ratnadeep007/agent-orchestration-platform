from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg import Connection
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from app.db import get_connection
from app.openclaw_bridge import sync_agent_to_openclaw

router = APIRouter(prefix="/agents", tags=["agents"])


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


class AgentRepository:
    def __init__(self, connection: Connection):
        self.connection = connection

    def list(self) -> list[dict[str, Any]]:
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT * FROM agents ORDER BY created_at DESC")
            return list(cursor.fetchall())

    def get(self, agent_id: UUID) -> dict[str, Any] | None:
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT * FROM agents WHERE id = %s", (agent_id,))
            return cursor.fetchone()

    def create(self, payload: AgentCreate) -> dict[str, Any]:
        data = payload.model_dump()
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO agents (
                    name, role, system_prompt, model, tools, channels, schedules,
                    memory, skills, interaction_rules, guardrails
                )
                VALUES (
                    %(name)s, %(role)s, %(system_prompt)s, %(model)s, %(tools)s,
                    %(channels)s, %(schedules)s, %(memory)s, %(skills)s,
                    %(interaction_rules)s, %(guardrails)s
                )
                RETURNING *
                """,
                _json_payload(data),
            )
            row = cursor.fetchone()
        self.connection.commit()
        return row

    def update(self, agent_id: UUID, payload: AgentUpdate) -> dict[str, Any] | None:
        data = payload.model_dump()
        data["id"] = agent_id
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE agents
                SET
                    name = %(name)s,
                    role = %(role)s,
                    system_prompt = %(system_prompt)s,
                    model = %(model)s,
                    tools = %(tools)s,
                    channels = %(channels)s,
                    schedules = %(schedules)s,
                    memory = %(memory)s,
                    skills = %(skills)s,
                    interaction_rules = %(interaction_rules)s,
                    guardrails = %(guardrails)s,
                    sync_status = 'pending',
                    updated_at = now()
                WHERE id = %(id)s
                RETURNING *
                """,
                _json_payload(data),
            )
            row = cursor.fetchone()
        self.connection.commit()
        return row

    def delete(self, agent_id: UUID) -> bool:
        with self.connection.cursor() as cursor:
            cursor.execute("DELETE FROM agents WHERE id = %s", (agent_id,))
            deleted = cursor.rowcount > 0
        self.connection.commit()
        return deleted

    def mark_synced(
        self,
        agent_id: UUID,
        openclaw_agent_id: str,
        openclaw_workspace_path: str,
    ) -> dict[str, Any] | None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE agents
                SET
                    sync_status = 'synced',
                    openclaw_agent_id = %s,
                    openclaw_workspace_path = %s,
                    last_synced_at = now(),
                    updated_at = now()
                WHERE id = %s
                RETURNING *
                """,
                (openclaw_agent_id, openclaw_workspace_path, agent_id),
            )
            row = cursor.fetchone()
        self.connection.commit()
        return row


def _json_payload(data: dict[str, Any]) -> dict[str, Any]:
    json_fields = {
        "tools",
        "channels",
        "schedules",
        "memory",
        "skills",
        "interaction_rules",
        "guardrails",
    }
    return {
        key: Jsonb(value) if key in json_fields else value
        for key, value in data.items()
    }


def _serialize(row: dict[str, Any]) -> Agent:
    payload = dict(row)
    payload["created_at"] = payload["created_at"].isoformat()
    payload["updated_at"] = payload["updated_at"].isoformat()
    if payload.get("last_synced_at"):
        payload["last_synced_at"] = payload["last_synced_at"].isoformat()
    return Agent.model_validate(payload)


def get_agent_repository(
    connection: Connection = Depends(get_connection),
) -> AgentRepository:
    return AgentRepository(connection)


@router.get("", response_model=list[Agent])
def list_agents(repository: AgentRepository = Depends(get_agent_repository)) -> list[Agent]:
    return [_serialize(row) for row in repository.list()]


@router.post("", response_model=Agent, status_code=status.HTTP_201_CREATED)
def create_agent(
    payload: AgentCreate,
    repository: AgentRepository = Depends(get_agent_repository),
) -> Agent:
    return _serialize(repository.create(payload))


@router.get("/{agent_id}", response_model=Agent)
def get_agent(
    agent_id: UUID,
    repository: AgentRepository = Depends(get_agent_repository),
) -> Agent:
    row = repository.get(agent_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return _serialize(row)


@router.put("/{agent_id}", response_model=Agent)
def update_agent(
    agent_id: UUID,
    payload: AgentUpdate,
    repository: AgentRepository = Depends(get_agent_repository),
) -> Agent:
    row = repository.update(agent_id, payload)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return _serialize(row)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(
    agent_id: UUID,
    repository: AgentRepository = Depends(get_agent_repository),
) -> None:
    if not repository.delete(agent_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")


@router.post("/{agent_id}/sync-openclaw", response_model=AgentSyncResult)
def sync_agent(
    agent_id: UUID,
    repository: AgentRepository = Depends(get_agent_repository),
) -> AgentSyncResult:
    row = repository.get(agent_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    result = sync_agent_to_openclaw(row)
    synced = repository.mark_synced(
        agent_id,
        result["openclaw_agent_id"],
        result["openclaw_workspace_path"],
    )
    if not synced:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    return AgentSyncResult(
        agent=_serialize(synced),
        openclaw_agent_id=result["openclaw_agent_id"],
        openclaw_workspace_path=result["openclaw_workspace_path"],
        local_workspace_path=result["local_workspace_path"],
        files=result["files"],
    )
