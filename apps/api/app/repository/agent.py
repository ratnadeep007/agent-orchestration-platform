from typing import Any
from uuid import UUID

from fastapi import Depends
from psycopg import Connection
from psycopg.types.json import Jsonb

from app.db import get_connection
from app.models.agent import AgentCreate, AgentUpdate


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


def get_agent_repository(
    connection: Connection = Depends(get_connection),
) -> AgentRepository:
    return AgentRepository(connection)


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
