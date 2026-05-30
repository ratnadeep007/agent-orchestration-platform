from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class WorkflowGraph(BaseModel):
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    openclaw: dict[str, Any] = Field(default_factory=dict)


class WorkflowBase(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    graph: WorkflowGraph = Field(default_factory=WorkflowGraph)
    status: str = "draft"
    telegram_command: str | None = None


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


class WorkflowCostRecord(BaseModel):
    id: UUID
    run_id: UUID
    agent_id: UUID | None
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_cost: float
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
    costs: list[WorkflowCostRecord] = Field(default_factory=list)
