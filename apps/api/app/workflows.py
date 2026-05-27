from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg import Connection
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from app.db import get_connection

router = APIRouter(prefix="/workflows", tags=["workflows"])


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


def get_workflow_repository(
    connection: Connection = Depends(get_connection),
) -> WorkflowRepository:
    return WorkflowRepository(connection)


def _workflow_payload(payload: WorkflowBase) -> dict[str, Any]:
    data = payload.model_dump()
    data["graph"] = Jsonb(data["graph"])
    return data


def _serialize_workflow(row: dict[str, Any]) -> Workflow:
    payload = dict(row)
    payload["created_at"] = payload["created_at"].isoformat()
    payload["updated_at"] = payload["updated_at"].isoformat()
    return Workflow.model_validate(payload)


def _serialize_template(row: dict[str, Any]) -> WorkflowTemplate:
    payload = dict(row)
    payload["created_at"] = payload["created_at"].isoformat()
    return WorkflowTemplate.model_validate(payload)


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
