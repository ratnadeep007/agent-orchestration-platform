from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.workflows import WorkflowCreate, WorkflowUpdate, get_workflow_repository


class FakeWorkflowRepository:
    def __init__(self) -> None:
        template_id = uuid4()
        self.rows = {}
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


def _workflow_row(data):
    now = datetime.now(UTC)
    return {
        "id": uuid4(),
        "created_at": now,
        "updated_at": now,
        **data,
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
