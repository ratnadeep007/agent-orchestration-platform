from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.bus.message import get_message_bus
from app.config import settings
from app.main import app
from app.models.message import RuntimeEventCreate
from app.repository.workflow import get_workflow_repository, get_workflow_run_bus
from app.routes.telegram import get_telegram_message_repository


class FakeTelegramMessageRepository:
    def __init__(self) -> None:
        self.rows = {}

    def mirror_event(self, payload: RuntimeEventCreate):
        for row in self.rows.values():
            if row["channel"] == payload.channel and row["external_id"] == payload.external_id:
                return row

        row = {
            "id": uuid4(),
            "created_at": datetime.now(UTC),
            "run_id": payload.run_id,
            "agent_id": payload.agent_id,
            "channel": payload.channel,
            "direction": payload.direction,
            "body": payload.body,
            "external_id": payload.external_id,
            "delivery_state": payload.delivery_state,
            "metadata": {
                **payload.metadata,
                "source": payload.source,
                "event_type": payload.event_type,
            },
        }
        self.rows[row["id"]] = row
        return row

    def create_outbound(self, *, channel: str, body: str, metadata):
        row = {
            "id": uuid4(),
            "created_at": datetime.now(UTC),
            "run_id": None,
            "agent_id": None,
            "channel": channel,
            "direction": "outbound",
            "body": body,
            "external_id": None,
            "delivery_state": "queued",
            "metadata": metadata,
        }
        self.rows[row["id"]] = row
        return row

    def attach_run(self, message_id: UUID, run_id: UUID):
        row = self.rows[message_id]
        row["run_id"] = run_id
        return row


class FakeWorkflowRepository:
    def __init__(self) -> None:
        self.run_id = uuid4()
        self.started = []
        self.command_map = {}

    def create_run(self, workflow_id: UUID, payload):
        self.started.append((workflow_id, payload))
        return {
            "id": self.run_id,
            "workflow_id": workflow_id,
            "status": "queued",
            "graph_snapshot": {"nodes": [], "edges": [], "openclaw": {}},
            "trigger": payload.trigger,
            "started_at": None,
            "completed_at": None,
            "error": None,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
            "nodes": [],
            "logs": [],
        }

    def get_by_telegram_command(self, command: str):
        workflow_id = self.command_map.get(command)
        if workflow_id is None:
            return None
        return {
            "id": workflow_id,
            "telegram_command": command,
        }


class FakeMessageBus:
    def __init__(self) -> None:
        self.enqueued = []

    def enqueue(self, message_id: UUID) -> None:
        self.enqueued.append(message_id)


def test_telegram_webhook_mirrors_inbound_message():
    repository = FakeTelegramMessageRepository()
    workflow_repository = FakeWorkflowRepository()
    workflow_bus = FakeMessageBus()
    original_secret = settings.telegram_webhook_secret
    original_allowed_chat_id = settings.telegram_allowed_chat_id
    original_workflow_id = settings.telegram_workflow_id
    settings.telegram_webhook_secret = ""
    settings.telegram_allowed_chat_id = ""
    settings.telegram_workflow_id = ""
    app.dependency_overrides[get_telegram_message_repository] = lambda: repository
    app.dependency_overrides[get_workflow_repository] = lambda: workflow_repository
    app.dependency_overrides[get_workflow_run_bus] = lambda: workflow_bus

    try:
        client = TestClient(app)
        response = client.post(
            "/telegram/webhook",
            json={
                "update_id": 10,
                "message": {
                    "message_id": 20,
                    "chat": {"id": 12345},
                    "from": {"id": 99},
                    "text": "hello",
                },
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["accepted"] is True
        assert body["message"]["channel"] == "telegram"
        assert body["message"]["direction"] == "inbound"
        assert body["message"]["body"] == "hello"
        assert body["message"]["external_id"] == "telegram:12345:20"
        assert body["workflow_run_id"] is None
        assert workflow_repository.started == []
        assert workflow_bus.enqueued == []
    finally:
        settings.telegram_webhook_secret = original_secret
        settings.telegram_allowed_chat_id = original_allowed_chat_id
        settings.telegram_workflow_id = original_workflow_id
        app.dependency_overrides.clear()


def test_telegram_webhook_starts_configured_workflow():
    repository = FakeTelegramMessageRepository()
    workflow_repository = FakeWorkflowRepository()
    workflow_bus = FakeMessageBus()
    workflow_id = uuid4()
    original_secret = settings.telegram_webhook_secret
    original_allowed_chat_id = settings.telegram_allowed_chat_id
    original_workflow_id = settings.telegram_workflow_id
    settings.telegram_webhook_secret = ""
    settings.telegram_allowed_chat_id = ""
    settings.telegram_workflow_id = str(workflow_id)
    app.dependency_overrides[get_telegram_message_repository] = lambda: repository
    app.dependency_overrides[get_workflow_repository] = lambda: workflow_repository
    app.dependency_overrides[get_workflow_run_bus] = lambda: workflow_bus

    try:
        client = TestClient(app)
        response = client.post(
            "/telegram/webhook",
            json={
                "update_id": 10,
                "message": {
                    "message_id": 20,
                    "chat": {"id": 12345},
                    "from": {"id": 99},
                    "text": "run this",
                },
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert UUID(body["workflow_run_id"]) == workflow_repository.run_id
        assert UUID(body["message"]["run_id"]) == workflow_repository.run_id
        assert workflow_repository.started[0][0] == workflow_id
        assert workflow_repository.started[0][1].trigger["source"] == "telegram"
        assert workflow_repository.started[0][1].trigger["chat_id"] == "12345"
        assert workflow_repository.started[0][1].trigger["text"] == "run this"
        assert workflow_repository.started[0][1].trigger["telegram_command"] is None
        assert workflow_repository.started[0][1].trigger["command_args"] == "run this"
        assert workflow_bus.enqueued == [workflow_repository.run_id]

        duplicate = client.post(
            "/telegram/webhook",
            json={
                "update_id": 10,
                "message": {
                    "message_id": 20,
                    "chat": {"id": 12345},
                    "from": {"id": 99},
                    "text": "run this",
                },
            },
        )
        assert duplicate.status_code == 200
        assert UUID(duplicate.json()["workflow_run_id"]) == workflow_repository.run_id
        assert len(workflow_repository.started) == 1
        assert workflow_bus.enqueued == [workflow_repository.run_id]
    finally:
        settings.telegram_webhook_secret = original_secret
        settings.telegram_allowed_chat_id = original_allowed_chat_id
        settings.telegram_workflow_id = original_workflow_id
        app.dependency_overrides.clear()


def test_telegram_webhook_ignores_invalid_workflow_id():
    repository = FakeTelegramMessageRepository()
    workflow_repository = FakeWorkflowRepository()
    workflow_bus = FakeMessageBus()
    original_secret = settings.telegram_webhook_secret
    original_allowed_chat_id = settings.telegram_allowed_chat_id
    original_workflow_id = settings.telegram_workflow_id
    settings.telegram_webhook_secret = ""
    settings.telegram_allowed_chat_id = ""
    settings.telegram_workflow_id = "not-a-uuid"
    app.dependency_overrides[get_telegram_message_repository] = lambda: repository
    app.dependency_overrides[get_workflow_repository] = lambda: workflow_repository
    app.dependency_overrides[get_workflow_run_bus] = lambda: workflow_bus

    try:
        client = TestClient(app)
        response = client.post(
            "/telegram/webhook",
            json={
                "update_id": 10,
                "message": {
                    "message_id": 20,
                    "chat": {"id": 12345},
                    "from": {"id": 99},
                    "text": "ignored",
                },
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["accepted"] is True
        assert body["workflow_run_id"] is None
        assert workflow_repository.started == []
        assert workflow_bus.enqueued == []
    finally:
        settings.telegram_webhook_secret = original_secret
        settings.telegram_allowed_chat_id = original_allowed_chat_id
        settings.telegram_workflow_id = original_workflow_id
        app.dependency_overrides.clear()


def test_telegram_webhook_routes_command_to_mapped_workflow():
    repository = FakeTelegramMessageRepository()
    workflow_repository = FakeWorkflowRepository()
    workflow_bus = FakeMessageBus()
    mapped_workflow_id = uuid4()
    workflow_repository.command_map["research"] = mapped_workflow_id
    original_secret = settings.telegram_webhook_secret
    original_allowed_chat_id = settings.telegram_allowed_chat_id
    original_workflow_id = settings.telegram_workflow_id
    settings.telegram_webhook_secret = ""
    settings.telegram_allowed_chat_id = ""
    settings.telegram_workflow_id = str(uuid4())
    app.dependency_overrides[get_telegram_message_repository] = lambda: repository
    app.dependency_overrides[get_workflow_repository] = lambda: workflow_repository
    app.dependency_overrides[get_workflow_run_bus] = lambda: workflow_bus

    try:
        client = TestClient(app)
        response = client.post(
            "/telegram/webhook",
            json={
                "update_id": 10,
                "message": {
                    "message_id": 20,
                    "chat": {"id": 12345},
                    "from": {"id": 99},
                    "text": "/research find facts",
                },
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert UUID(body["workflow_run_id"]) == workflow_repository.run_id
        assert workflow_repository.started[0][0] == mapped_workflow_id
        assert workflow_repository.started[0][1].trigger["telegram_command"] == "research"
        assert workflow_repository.started[0][1].trigger["command_args"] == "find facts"
        assert workflow_bus.enqueued == [workflow_repository.run_id]
    finally:
        settings.telegram_webhook_secret = original_secret
        settings.telegram_allowed_chat_id = original_allowed_chat_id
        settings.telegram_workflow_id = original_workflow_id
        app.dependency_overrides.clear()


def test_telegram_webhook_ignores_unknown_command_without_fallback():
    repository = FakeTelegramMessageRepository()
    workflow_repository = FakeWorkflowRepository()
    workflow_bus = FakeMessageBus()
    original_secret = settings.telegram_webhook_secret
    original_allowed_chat_id = settings.telegram_allowed_chat_id
    original_workflow_id = settings.telegram_workflow_id
    settings.telegram_webhook_secret = ""
    settings.telegram_allowed_chat_id = ""
    settings.telegram_workflow_id = str(uuid4())
    app.dependency_overrides[get_telegram_message_repository] = lambda: repository
    app.dependency_overrides[get_workflow_repository] = lambda: workflow_repository
    app.dependency_overrides[get_workflow_run_bus] = lambda: workflow_bus

    try:
        client = TestClient(app)
        response = client.post(
            "/telegram/webhook",
            json={
                "update_id": 10,
                "message": {
                    "message_id": 20,
                    "chat": {"id": 12345},
                    "from": {"id": 99},
                    "text": "/unknown do not route",
                },
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["workflow_run_id"] is None
        assert workflow_repository.started == []
        assert workflow_bus.enqueued == []
    finally:
        settings.telegram_webhook_secret = original_secret
        settings.telegram_allowed_chat_id = original_allowed_chat_id
        settings.telegram_workflow_id = original_workflow_id
        app.dependency_overrides.clear()


def test_telegram_outbound_message_is_queued():
    repository = FakeTelegramMessageRepository()
    bus = FakeMessageBus()
    original_allowed_chat_id = settings.telegram_allowed_chat_id
    settings.telegram_allowed_chat_id = ""
    app.dependency_overrides[get_telegram_message_repository] = lambda: repository
    app.dependency_overrides[get_message_bus] = lambda: bus

    try:
        client = TestClient(app)
        response = client.post(
            "/telegram/messages",
            json={"chat_id": "12345", "body": "reply", "metadata": {"source": "test"}},
        )

        assert response.status_code == 202
        body = response.json()
        assert body["delivery_state"] == "queued"
        assert body["metadata"] == {"source": "test", "chat_id": "12345"}
        assert bus.enqueued == [UUID(body["id"])]
    finally:
        settings.telegram_allowed_chat_id = original_allowed_chat_id
        app.dependency_overrides.clear()
