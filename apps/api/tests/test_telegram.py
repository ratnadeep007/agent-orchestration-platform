from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.messages import RuntimeEventCreate, get_message_bus
from app.telegram import get_telegram_message_repository


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


class FakeMessageBus:
    def __init__(self) -> None:
        self.enqueued = []

    def enqueue(self, message_id: UUID) -> None:
        self.enqueued.append(message_id)


def test_telegram_webhook_mirrors_inbound_message():
    repository = FakeTelegramMessageRepository()
    original_secret = settings.telegram_webhook_secret
    original_allowed_chat_id = settings.telegram_allowed_chat_id
    settings.telegram_webhook_secret = ""
    settings.telegram_allowed_chat_id = ""
    app.dependency_overrides[get_telegram_message_repository] = lambda: repository

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
    finally:
        settings.telegram_webhook_secret = original_secret
        settings.telegram_allowed_chat_id = original_allowed_chat_id
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
