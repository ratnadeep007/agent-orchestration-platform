from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg import Connection
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field
from redis import Redis

from app.config import settings
from app.db import get_connection

router = APIRouter(prefix="/workflows", tags=["workflows"])
WORKFLOW_RUN_QUEUE = "workflow_run_execution"


class WorkflowGraph(BaseModel):
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    openclaw: dict[str, Any] = Field(default_factory=dict)


class WorkflowBase(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    graph: WorkflowGraph = Field(default_factory=WorkflowGraph)
    status: str = "draft"


class WorkflowCreate(WorkflowBase):
    pass


class WorkflowUpdate(WorkflowBase):
    pass


class Workflow(WorkflowBase):
    id: UUID
    created_at: str
    updated_at: str


class WorkflowTemplate(BaseModel):
    id: UUID
    name: str
    description: str
    graph: WorkflowGraph
    created_at: str


class WorkflowRunCreate(BaseModel):
    trigger: dict[str, Any] = Field(default_factory=dict)


class WorkflowRunNode(BaseModel):
    id: UUID
    run_id: UUID
    node_id: str
    node_type: str
    label: str
    status: str
    input: dict[str, Any]
    output: dict[str, Any]
    error: str | None
    started_at: str | None
    completed_at: str | None
    created_at: str
    updated_at: str


class WorkflowRunLog(BaseModel):
    id: UUID
    run_id: UUID | None
    level: str
    message: str
    metadata: dict[str, Any]
    created_at: str


class WorkflowRun(BaseModel):
    id: UUID
    workflow_id: UUID | None
    status: str
    graph_snapshot: WorkflowGraph
    trigger: dict[str, Any]
    started_at: str | None
    completed_at: str | None
    error: str | None
    created_at: str
    updated_at: str
    nodes: list[WorkflowRunNode] = Field(default_factory=list)
    logs: list[WorkflowRunLog] = Field(default_factory=list)


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

            graph = _normalize_graph(workflow["graph"])
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
            return {**row, "nodes": nodes, "logs": logs}


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
    return data


def _normalize_graph(graph: dict[str, Any]) -> dict[str, Any]:
    return {
        "nodes": graph["nodes"] if isinstance(graph.get("nodes"), list) else [],
        "edges": graph["edges"] if isinstance(graph.get("edges"), list) else [],
        "openclaw": graph["openclaw"] if isinstance(graph.get("openclaw"), dict) else {},
    }


def _serialize_workflow(row: dict[str, Any]) -> Workflow:
    payload = dict(row)
    payload["created_at"] = payload["created_at"].isoformat()
    payload["updated_at"] = payload["updated_at"].isoformat()
    return Workflow.model_validate(payload)


def _serialize_template(row: dict[str, Any]) -> WorkflowTemplate:
    payload = dict(row)
    payload["created_at"] = payload["created_at"].isoformat()
    return WorkflowTemplate.model_validate(payload)


def _serialize_run(row: dict[str, Any]) -> WorkflowRun:
    payload = dict(row)
    for field in ["started_at", "completed_at", "created_at", "updated_at"]:
        if payload[field] is not None:
            payload[field] = payload[field].isoformat()
    payload["nodes"] = [_serialize_run_node(node).model_dump() for node in payload["nodes"]]
    payload["logs"] = [_serialize_run_log(log).model_dump() for log in payload["logs"]]
    return WorkflowRun.model_validate(payload)


def _serialize_run_node(row: dict[str, Any]) -> WorkflowRunNode:
    payload = dict(row)
    for field in ["started_at", "completed_at", "created_at", "updated_at"]:
        if payload[field] is not None:
            payload[field] = payload[field].isoformat()
    return WorkflowRunNode.model_validate(payload)


def _serialize_run_log(row: dict[str, Any]) -> WorkflowRunLog:
    payload = dict(row)
    payload["created_at"] = payload["created_at"].isoformat()
    return WorkflowRunLog.model_validate(payload)


@router.get("", response_model=list[Workflow])
def list_workflows(
    repository: WorkflowRepository = Depends(get_workflow_repository),
) -> list[Workflow]:
    return [_serialize_workflow(row) for row in repository.list()]


@router.post("", response_model=Workflow, status_code=status.HTTP_201_CREATED)
def create_workflow(
    payload: WorkflowCreate,
    repository: WorkflowRepository = Depends(get_workflow_repository),
) -> Workflow:
    return _serialize_workflow(repository.create(payload))


@router.get("/templates", response_model=list[WorkflowTemplate])
def list_workflow_templates(
    repository: WorkflowRepository = Depends(get_workflow_repository),
) -> list[WorkflowTemplate]:
    return [_serialize_template(row) for row in repository.list_templates()]


@router.post("/templates/{template_id}/instantiate", response_model=Workflow)
def instantiate_workflow_template(
    template_id: UUID,
    repository: WorkflowRepository = Depends(get_workflow_repository),
) -> Workflow:
    row = repository.instantiate_template(template_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return _serialize_workflow(row)


@router.get("/{workflow_id}", response_model=Workflow)
def get_workflow(
    workflow_id: UUID,
    repository: WorkflowRepository = Depends(get_workflow_repository),
) -> Workflow:
    row = repository.get(workflow_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    return _serialize_workflow(row)


@router.get("/{workflow_id}/runs", response_model=list[WorkflowRun])
def list_workflow_runs(
    workflow_id: UUID,
    repository: WorkflowRepository = Depends(get_workflow_repository),
) -> list[WorkflowRun]:
    if not repository.get(workflow_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    return [_serialize_run(row) for row in repository.list_runs(workflow_id)]


@router.post("/{workflow_id}/runs", response_model=WorkflowRun, status_code=status.HTTP_202_ACCEPTED)
def start_workflow_run(
    workflow_id: UUID,
    payload: WorkflowRunCreate,
    repository: WorkflowRepository = Depends(get_workflow_repository),
    bus: WorkflowRunBus = Depends(get_workflow_run_bus),
) -> WorkflowRun:
    row = repository.create_run(workflow_id, payload)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    bus.enqueue(row["id"])
    return _serialize_run(row)


@router.get("/{workflow_id}/runs/{run_id}", response_model=WorkflowRun)
def get_workflow_run(
    workflow_id: UUID,
    run_id: UUID,
    repository: WorkflowRepository = Depends(get_workflow_repository),
) -> WorkflowRun:
    row = repository.get_run(run_id)
    if not row or row["workflow_id"] != workflow_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow run not found")
    return _serialize_run(row)


@router.put("/{workflow_id}", response_model=Workflow)
def update_workflow(
    workflow_id: UUID,
    payload: WorkflowUpdate,
    repository: WorkflowRepository = Depends(get_workflow_repository),
) -> Workflow:
    row = repository.update(workflow_id, payload)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    return _serialize_workflow(row)


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workflow(
    workflow_id: UUID,
    repository: WorkflowRepository = Depends(get_workflow_repository),
) -> None:
    if not repository.delete(workflow_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
