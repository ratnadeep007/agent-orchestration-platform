from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.models.workflow import WorkflowCreate, WorkflowRunCreate, WorkflowUpdate
from app.repository.workflow import get_workflow_repository, get_workflow_run_bus


class FakeWorkflowRepository:
    def __init__(self) -> None:
        template_id = uuid4()
        self.rows = {}
        self.runs = {}
        self.templates = {
            template_id: _template_row(
                template_id,
                "Research Brief",
                {
                    "nodes": [{"id": "researcher", "type": "agent"}],
                    "edges": [],
                    "openclaw": {"strategy": "orchestrator-delegates"},
                },
            )
        }

    def list(self):
        return list(self.rows.values())

    def get(self, workflow_id: UUID):
        return self.rows.get(workflow_id)

    def create(self, payload: WorkflowCreate):
        row = _workflow_row(payload.model_dump())
        self.rows[row["id"]] = row
        return row

    def update(self, workflow_id: UUID, payload: WorkflowUpdate):
        if workflow_id not in self.rows:
            return None
        row = self.rows[workflow_id] | payload.model_dump() | {"updated_at": datetime.now(UTC)}
        self.rows[workflow_id] = row
        return row

    def delete(self, workflow_id: UUID):
        return self.rows.pop(workflow_id, None) is not None

    def list_templates(self):
        return list(self.templates.values())

    def instantiate_template(self, template_id: UUID):
        template = self.templates.get(template_id)
        if not template:
            return None
        row = _workflow_row(
            {
                "name": template["name"],
                "description": template["description"],
                "graph": template["graph"],
                "status": "draft",
            }
        )
        self.rows[row["id"]] = row
        return row

    def create_run(self, workflow_id: UUID, payload: WorkflowRunCreate):
        workflow = self.rows.get(workflow_id)
        if not workflow:
            return None
        run = _run_row(workflow, payload.trigger)
        self.runs[run["id"]] = run
        return run

    def list_runs(self, workflow_id: UUID):
        return [run for run in self.runs.values() if run["workflow_id"] == workflow_id]

    def get_run(self, run_id: UUID):
        return self.runs.get(run_id)


class FakeWorkflowRunBus:
    def __init__(self) -> None:
        self.enqueued = []

    def enqueue(self, run_id: UUID) -> None:
        self.enqueued.append(run_id)


def _workflow_row(data):
    now = datetime.now(UTC)
    return {
        "id": uuid4(),
        "created_at": now,
        "updated_at": now,
        **data,
    }


def _run_row(workflow, trigger):
    now = datetime.now(UTC)
    run_id = uuid4()
    return {
        "id": run_id,
        "workflow_id": workflow["id"],
        "status": "queued",
        "graph_snapshot": workflow["graph"],
        "trigger": trigger,
        "started_at": None,
        "completed_at": None,
        "error": None,
        "created_at": now,
        "updated_at": now,
        "nodes": [
            {
                "id": uuid4(),
                "run_id": run_id,
                "node_id": node["id"],
                "node_type": node.get("type", "agent"),
                "label": node.get("label", node["id"]),
                "status": "queued",
                "input": {},
                "output": {},
                "error": None,
                "started_at": None,
                "completed_at": None,
                "created_at": now,
                "updated_at": now,
            }
            for node in workflow["graph"]["nodes"]
        ],
        "logs": [
            {
                "id": uuid4(),
                "run_id": run_id,
                "level": "info",
                "message": "workflow run queued",
                "metadata": {"source": "test"},
                "created_at": now,
            }
        ],
    }


def _template_row(template_id, name, graph):
    return {
        "id": template_id,
        "name": name,
        "description": "Template description",
        "graph": graph,
        "created_at": datetime.now(UTC),
    }


def test_workflow_crud_routes():
    repository = FakeWorkflowRepository()
    app.dependency_overrides[get_workflow_repository] = lambda: repository

    try:
        client = TestClient(app)
        payload = {
            "name": "Manual Workflow",
            "description": "Saved from builder",
            "status": "draft",
            "graph": {
                "nodes": [{"id": "planner", "type": "agent"}],
                "edges": [{"id": "e1", "source": "planner", "target": "done"}],
                "openclaw": {"strategy": "orchestrator-delegates"},
            },
        }

        create_response = client.post("/workflows", json=payload)
        assert create_response.status_code == 201
        created = create_response.json()
        assert created["name"] == "Manual Workflow"
        assert created["graph"]["nodes"][0]["id"] == "planner"

        update_response = client.put(
            f"/workflows/{created['id']}",
            json={**payload, "name": "Updated Workflow"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["name"] == "Updated Workflow"

        assert client.get("/workflows").json()[0]["name"] == "Updated Workflow"
        assert client.delete(f"/workflows/{created['id']}").status_code == 204
        assert client.get(f"/workflows/{created['id']}").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_workflow_run_routes_enqueue_and_return_node_state():
    repository = FakeWorkflowRepository()
    bus = FakeWorkflowRunBus()
    app.dependency_overrides[get_workflow_repository] = lambda: repository
    app.dependency_overrides[get_workflow_run_bus] = lambda: bus

    try:
        client = TestClient(app)
        create_response = client.post(
            "/workflows",
            json={
                "name": "Executable Workflow",
                "description": "Run me",
                "status": "draft",
                "graph": {
                    "nodes": [{"id": "planner", "type": "agent", "label": "Planner"}],
                    "edges": [],
                    "openclaw": {},
                },
            },
        )
        workflow_id = create_response.json()["id"]

        run_response = client.post(
            f"/workflows/{workflow_id}/runs",
            json={"trigger": {"source": "test"}},
        )

        assert run_response.status_code == 202
        run = run_response.json()
        assert run["status"] == "queued"
        assert run["trigger"] == {"source": "test"}
        assert run["nodes"][0]["node_id"] == "planner"
        assert run["logs"][0]["message"] == "workflow run queued"
        assert bus.enqueued == [UUID(run["id"])]

        list_response = client.get(f"/workflows/{workflow_id}/runs")
        assert list_response.status_code == 200
        assert list_response.json()[0]["id"] == run["id"]

        get_response = client.get(f"/workflows/{workflow_id}/runs/{run['id']}")
        assert get_response.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_template_instantiation_route():
    repository = FakeWorkflowRepository()
    app.dependency_overrides[get_workflow_repository] = lambda: repository

    try:
        client = TestClient(app)
        templates = client.get("/workflows/templates").json()
        response = client.post(f"/workflows/templates/{templates[0]['id']}/instantiate")

        assert response.status_code == 200
        workflow = response.json()
        assert workflow["name"] == "Research Brief"
        assert workflow["graph"]["openclaw"]["strategy"] == "orchestrator-delegates"
    finally:
        app.dependency_overrides.clear()
