from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import Depends
from psycopg import Connection
from psycopg.types.json import Jsonb
from redis import Redis

from app.config import settings
from app.db import get_connection
from app.models.workflow import WorkflowBase, WorkflowCreate, WorkflowRunCreate, WorkflowUpdate

WORKFLOW_RUN_QUEUE = "workflow_run_execution"


class WorkflowRepository:
    def __init__(self, connection: Connection):
        self.connection = connection

    def list(self) -> list[dict[str, Any]]:
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT * FROM workflows ORDER BY created_at DESC")
            return list(cursor.fetchall())

    def get(self, workflow_id: UUID) -> dict[str, Any] | None:
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT * FROM workflows WHERE id = %s", (workflow_id,))
            return cursor.fetchone()

    def get_by_telegram_command(self, command: str) -> dict[str, Any] | None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM workflows
                WHERE telegram_command = %s
                """,
                (command,),
            )
            return cursor.fetchone()

    def create(self, payload: WorkflowCreate) -> dict[str, Any]:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO workflows (name, description, graph, status)
                VALUES (%(name)s, %(description)s, %(graph)s, %(status)s)
                RETURNING *
                """,
                _workflow_payload(payload),
            )
            row = cursor.fetchone()
        self.connection.commit()
        return row

    def update(self, workflow_id: UUID, payload: WorkflowUpdate) -> dict[str, Any] | None:
        data = _workflow_payload(payload)
        data["id"] = workflow_id
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE workflows
                SET
                    name = %(name)s,
                    description = %(description)s,
                    graph = %(graph)s,
                    status = %(status)s,
                    updated_at = now()
                WHERE id = %(id)s
                RETURNING *
                """,
                data,
            )
            row = cursor.fetchone()
        self.connection.commit()
        return row

    def delete(self, workflow_id: UUID) -> bool:
        with self.connection.cursor() as cursor:
            cursor.execute("DELETE FROM workflows WHERE id = %s", (workflow_id,))
            deleted = cursor.rowcount > 0
        self.connection.commit()
        return deleted

    def list_templates(self) -> list[dict[str, Any]]:
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT * FROM workflow_templates ORDER BY name ASC")
            return list(cursor.fetchall())

    def instantiate_template(self, template_id: UUID) -> dict[str, Any] | None:
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT * FROM workflow_templates WHERE id = %s", (template_id,))
            template = cursor.fetchone()
            if not template:
                return None
            cursor.execute(
                """
                INSERT INTO workflows (name, description, graph, status)
                VALUES (%s, %s, %s, 'draft')
                RETURNING *
                """,
                (
                    template["name"],
                    template["description"],
                    Jsonb(template["graph"]),
                ),
            )
            row = cursor.fetchone()
        self.connection.commit()
        return row

    def create_run(self, workflow_id: UUID, payload: WorkflowRunCreate) -> dict[str, Any] | None:
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT * FROM workflows WHERE id = %s", (workflow_id,))
            workflow = cursor.fetchone()
            if not workflow:
                return None

            graph = normalize_workflow_graph(workflow["graph"])
            cursor.execute(
                """
                INSERT INTO workflow_runs (workflow_id, status, graph_snapshot, trigger)
                VALUES (%s, 'queued', %s, %s)
                RETURNING *
                """,
                (workflow_id, Jsonb(graph), Jsonb(payload.trigger)),
            )
            run = cursor.fetchone()

            for node in graph["nodes"]:
                cursor.execute(
                    """
                    INSERT INTO workflow_run_nodes (run_id, node_id, node_type, label)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        run["id"],
                        str(node["id"]),
                        str(node.get("type", "agent")),
                        str(node.get("label") or node["id"]),
                    ),
                )

        self.connection.commit()
        return self.get_run(run["id"])

    def list_runs(self, workflow_id: UUID) -> list[dict[str, Any]]:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM workflow_runs
                WHERE workflow_id = %s
                ORDER BY created_at DESC
                """,
                (workflow_id,),
            )
            return [self._with_nodes(row) for row in cursor.fetchall()]

    def get_run(self, run_id: UUID) -> dict[str, Any] | None:
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT * FROM workflow_runs WHERE id = %s", (run_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._with_nodes(row)

    def _with_nodes(self, row: dict[str, Any]) -> dict[str, Any]:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM workflow_run_nodes
                WHERE run_id = %s
                ORDER BY created_at ASC
                """,
                (row["id"],),
            )
            nodes = list(cursor.fetchall())
            cursor.execute(
                """
                SELECT *
                FROM run_logs
                WHERE run_id = %s
                ORDER BY created_at ASC
                """,
                (row["id"],),
            )
            logs = list(cursor.fetchall())
            cursor.execute(
                """
                SELECT *
                FROM cost_records
                WHERE run_id = %s
                ORDER BY created_at ASC
                """,
                (row["id"],),
            )
            costs = list(cursor.fetchall())
            return {**row, "nodes": nodes, "logs": logs, "costs": costs}


class WorkflowRunBus:
    def __init__(self, redis: Redis):
        self.redis = redis

    def enqueue(self, run_id: UUID) -> None:
        self.redis.lpush(WORKFLOW_RUN_QUEUE, str(run_id))


def get_workflow_repository(
    connection: Connection = Depends(get_connection),
) -> WorkflowRepository:
    return WorkflowRepository(connection)


def get_workflow_run_bus() -> WorkflowRunBus:
    return WorkflowRunBus(Redis.from_url(settings.redis_url))


def _workflow_payload(payload: WorkflowBase) -> dict[str, Any]:
    data = payload.model_dump()
    data["graph"] = Jsonb(data["graph"])
    data["telegram_command"] = _normalize_telegram_command(data.get("telegram_command"))
    return data


def normalize_workflow_graph(graph: dict[str, Any]) -> dict[str, Any]:
    return {
        "nodes": graph["nodes"] if isinstance(graph.get("nodes"), list) else [],
        "edges": graph["edges"] if isinstance(graph.get("edges"), list) else [],
        "openclaw": graph["openclaw"] if isinstance(graph.get("openclaw"), dict) else {},
    }


def _normalize_telegram_command(value: Any) -> str | None:
    if value is None:
        return None

    command = str(value).strip().lower()
    if not command:
        return None
    if command.startswith("/"):
        command = command[1:]
    if "@" in command:
        command = command.split("@", 1)[0]
    if not command or not all(ch.isalnum() or ch == "_" for ch in command):
        raise ValueError("telegram_command must contain only letters, numbers, and underscores")
    return command
