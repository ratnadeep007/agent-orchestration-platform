from app.models.workflow import (
    Workflow,
    WorkflowCostRecord,
    WorkflowRun,
    WorkflowRunLog,
    WorkflowRunNode,
    WorkflowTemplate,
)


def serialize_workflow(row: dict) -> Workflow:
    payload = dict(row)
    payload["created_at"] = payload["created_at"].isoformat()
    payload["updated_at"] = payload["updated_at"].isoformat()
    return Workflow.model_validate(payload)


def serialize_template(row: dict) -> WorkflowTemplate:
    payload = dict(row)
    payload["created_at"] = payload["created_at"].isoformat()
    return WorkflowTemplate.model_validate(payload)


def serialize_run(row: dict) -> WorkflowRun:
    payload = dict(row)
    for field in ["started_at", "completed_at", "created_at", "updated_at"]:
        if payload[field] is not None:
            payload[field] = payload[field].isoformat()
    payload["nodes"] = [serialize_run_node(node).model_dump() for node in payload["nodes"]]
    payload["logs"] = [serialize_run_log(log).model_dump() for log in payload["logs"]]
    payload["costs"] = [serialize_cost_record(cost).model_dump() for cost in payload["costs"]]
    return WorkflowRun.model_validate(payload)


def serialize_run_node(row: dict) -> WorkflowRunNode:
    payload = dict(row)
    for field in ["started_at", "completed_at", "created_at", "updated_at"]:
        if payload[field] is not None:
            payload[field] = payload[field].isoformat()
    return WorkflowRunNode.model_validate(payload)


def serialize_run_log(row: dict) -> WorkflowRunLog:
    payload = dict(row)
    payload["created_at"] = payload["created_at"].isoformat()
    return WorkflowRunLog.model_validate(payload)


def serialize_cost_record(row: dict) -> WorkflowCostRecord:
    payload = dict(row)
    payload["created_at"] = payload["created_at"].isoformat()
    payload["total_cost"] = float(payload["total_cost"])
    return WorkflowCostRecord.model_validate(payload)
