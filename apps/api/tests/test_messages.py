from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.bus.message import get_message_bus
from app.main import app
from app.models.message import MessageCreate, RuntimeEventCreate
from app.repository.message import get_message_repository


class FakeMessageRepository:
    def __init__(self) -> None:
        self.rows = {}

    def list(self, limit: int = 100):
        return list(self.rows.values())[:limit]

    def get(self, message_id: UUID):
        return self.rows.get(message_id)

    def create(self, payload: MessageCreate):
        row = {
            "id": uuid4(),
            "delivery_state": "queued",
            "created_at": datetime.now(UTC),
            **payload.model_dump(),
        }
        self.rows[row["id"]] = row
        return row

    def mirror_event(self, payload: RuntimeEventCreate):
        for row in self.rows.values():
            if row["channel"] == payload.channel and row["external_id"] == payload.external_id:
                return row

        metadata = {
            **payload.metadata,
            "source": payload.source,
            "event_type": payload.event_type,
        }
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
            "metadata": metadata,
        }
        self.rows[row["id"]] = row
        return row


class FakeMessageBus:
    def __init__(self) -> None:
        self.enqueued = []

    def enqueue(self, message_id: UUID) -> None:
        self.enqueued.append(message_id)


def test_message_create_persists_and_enqueues_delivery():
    repository = FakeMessageRepository()
    bus = FakeMessageBus()
    app.dependency_overrides[get_message_repository] = lambda: repository
    app.dependency_overrides[get_message_bus] = lambda: bus

    try:
        client = TestClient(app)
        response = client.post(
            "/messages",
            json={
                "channel": "telegram",
                "direction": "inbound",
                "body": "hello",
                "metadata": {"chat_id": "123"},
            },
        )

        assert response.status_code == 202
        body = response.json()
        assert body["delivery_state"] == "queued"
        assert body["metadata"] == {"chat_id": "123"}
        assert bus.enqueued == [UUID(body["id"])]
        assert client.get(f"/messages/{body['id']}").status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_runtime_event_mirror_persists_without_delivery_enqueue():
    repository = FakeMessageRepository()
    bus = FakeMessageBus()
    app.dependency_overrides[get_message_repository] = lambda: repository
    app.dependency_overrides[get_message_bus] = lambda: bus

    try:
        client = TestClient(app)
        payload = {
            "source": "openclaw",
            "event_type": "telegram.message.received",
            "channel": "telegram",
            "direction": "inbound",
            "body": "hello from telegram",
            "external_id": "telegram:message:1",
            "metadata": {"chat_id": "123"},
        }

        first = client.post("/messages/runtime-events", json=payload)
        second = client.post("/messages/runtime-events", json=payload)

        assert first.status_code == 202
        assert second.status_code == 202
        assert first.json()["id"] == second.json()["id"]
        assert first.json()["delivery_state"] == "mirrored"
        assert first.json()["metadata"]["source"] == "openclaw"
        assert first.json()["metadata"]["event_type"] == "telegram.message.received"
        assert bus.enqueued == []
    finally:
        app.dependency_overrides.clear()
