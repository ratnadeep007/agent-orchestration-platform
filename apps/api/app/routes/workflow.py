from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.workflow import Workflow, WorkflowCreate, WorkflowRun, WorkflowRunCreate, WorkflowTemplate, WorkflowUpdate
from app.repository.workflow import (
    WorkflowRepository,
    WorkflowRunBus,
    get_workflow_repository,
    get_workflow_run_bus,
    normalize_workflow_graph,
)
from app.serializers.workflow import serialize_run, serialize_template, serialize_workflow

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("", response_model=list[Workflow])
def list_workflows(
    repository: WorkflowRepository = Depends(get_workflow_repository),
) -> list[Workflow]:
    return [serialize_workflow(row) for row in repository.list()]


@router.post("", response_model=Workflow, status_code=status.HTTP_201_CREATED)
def create_workflow(
    payload: WorkflowCreate,
    repository: WorkflowRepository = Depends(get_workflow_repository),
) -> Workflow:
    return serialize_workflow(repository.create(payload))


@router.get("/templates", response_model=list[WorkflowTemplate])
def list_workflow_templates(
    repository: WorkflowRepository = Depends(get_workflow_repository),
) -> list[WorkflowTemplate]:
    return [serialize_template(row) for row in repository.list_templates()]


@router.post("/templates/{template_id}/instantiate", response_model=Workflow)
def instantiate_workflow_template(
    template_id: UUID,
    repository: WorkflowRepository = Depends(get_workflow_repository),
) -> Workflow:
    row = repository.instantiate_template(template_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return serialize_workflow(row)


@router.get("/{workflow_id}", response_model=Workflow)
def get_workflow(
    workflow_id: UUID,
    repository: WorkflowRepository = Depends(get_workflow_repository),
) -> Workflow:
    row = repository.get(workflow_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    return serialize_workflow(row)


@router.get("/{workflow_id}/runs", response_model=list[WorkflowRun])
def list_workflow_runs(
    workflow_id: UUID,
    repository: WorkflowRepository = Depends(get_workflow_repository),
) -> list[WorkflowRun]:
    if not repository.get(workflow_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    return [serialize_run(row) for row in repository.list_runs(workflow_id)]


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
    return serialize_run(row)


@router.get("/{workflow_id}/runs/{run_id}", response_model=WorkflowRun)
def get_workflow_run(
    workflow_id: UUID,
    run_id: UUID,
    repository: WorkflowRepository = Depends(get_workflow_repository),
) -> WorkflowRun:
    row = repository.get_run(run_id)
    if not row or row["workflow_id"] != workflow_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow run not found")
    return serialize_run(row)


@router.put("/{workflow_id}", response_model=Workflow)
def update_workflow(
    workflow_id: UUID,
    payload: WorkflowUpdate,
    repository: WorkflowRepository = Depends(get_workflow_repository),
) -> Workflow:
    row = repository.update(workflow_id, payload)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    return serialize_workflow(row)


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workflow(
    workflow_id: UUID,
    repository: WorkflowRepository = Depends(get_workflow_repository),
) -> None:
    if not repository.delete(workflow_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")


_normalize_graph = normalize_workflow_graph
