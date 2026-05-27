from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.agents import AgentCreate, AgentUpdate, get_agent_repository
from app.main import app


class FakeAgentRepository:
    def __init__(self) -> None:
        self.rows = {}

    def list(self):
        return list(self.rows.values())

    def get(self, agent_id: UUID):
        return self.rows.get(agent_id)

    def create(self, payload: AgentCreate):
        row = _row(payload.model_dump())
        self.rows[row["id"]] = row
        return row

    def update(self, agent_id: UUID, payload: AgentUpdate):
        if agent_id not in self.rows:
            return None
        row = self.rows[agent_id] | payload.model_dump() | {"sync_status": "pending"}
        row["updated_at"] = datetime.now(UTC)
        self.rows[agent_id] = row
        return row

    def delete(self, agent_id: UUID):
        return self.rows.pop(agent_id, None) is not None

    def mark_synced(
        self,
        agent_id: UUID,
        openclaw_agent_id: str,
        openclaw_workspace_path: str,
    ):
        if agent_id not in self.rows:
            return None
        row = self.rows[agent_id] | {
            "sync_status": "synced",
            "openclaw_agent_id": openclaw_agent_id,
            "openclaw_workspace_path": openclaw_workspace_path,
            "last_synced_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
        self.rows[agent_id] = row
        return row


def _row(data):
    now = datetime.now(UTC)
    return {
        "id": uuid4(),
        "sync_status": "pending",
        "created_at": now,
        "updated_at": now,
        "openclaw_agent_id": None,
        "openclaw_workspace_path": None,
        "last_synced_at": None,
        **data,
    }


def test_agent_crud_routes():
    repository = FakeAgentRepository()
    app.dependency_overrides[get_agent_repository] = lambda: repository

    try:
        client = TestClient(app)
        payload = {
            "name": "Planner",
            "role": "Plans tasks",
            "system_prompt": "Plan concise steps.",
            "model": "gpt-4.1-mini",
            "tools": ["search"],
            "channels": ["telegram"],
            "schedules": [],
            "memory": {"scope": "project"},
            "skills": ["planning"],
            "interaction_rules": ["ask when blocked"],
            "guardrails": ["no secrets"],
        }

        create_response = client.post("/agents", json=payload)
        assert create_response.status_code == 201
        created = create_response.json()
        assert created["name"] == "Planner"
        assert created["tools"] == ["search"]

        list_response = client.get("/agents")
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1

        update_response = client.put(
            f"/agents/{created['id']}",
            json={**payload, "name": "Executor"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["name"] == "Executor"

        delete_response = client.delete(f"/agents/{created['id']}")
        assert delete_response.status_code == 204
        assert client.get(f"/agents/{created['id']}").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_agent_sync_route_marks_agent_synced(monkeypatch):
    repository = FakeAgentRepository()
    app.dependency_overrides[get_agent_repository] = lambda: repository

    def fake_sync(row):
        return {
            "openclaw_agent_id": "app-planner-123",
            "openclaw_workspace_path": "/home/node/.openclaw/workspace/app-agents/123",
            "local_workspace_path": "/openclaw/workspace/app-agents/123",
            "files": ["/openclaw/workspace/app-agents/123/AGENTS.md"],
        }

    monkeypatch.setattr("app.agents.sync_agent_to_openclaw", fake_sync)

    try:
        client = TestClient(app)
        payload = {
            "name": "Planner",
            "role": "Plans tasks",
            "system_prompt": "Plan concise steps.",
            "model": "gpt-4.1-mini",
            "tools": ["search"],
            "channels": ["telegram"],
            "schedules": [],
            "memory": {"scope": "project"},
            "skills": ["planning"],
            "interaction_rules": ["ask when blocked"],
            "guardrails": ["no secrets"],
        }
        created = client.post("/agents", json=payload).json()

        response = client.post(f"/agents/{created['id']}/sync-openclaw")

        assert response.status_code == 200
        body = response.json()
        assert body["agent"]["sync_status"] == "synced"
        assert body["openclaw_agent_id"] == "app-planner-123"
        assert body["files"] == ["/openclaw/workspace/app-agents/123/AGENTS.md"]
    finally:
        app.dependency_overrides.clear()
