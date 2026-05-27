from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg import Connection
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field
from redis import Redis

from app.config import settings
from app.db import get_connection

router = APIRouter(prefix="/messages", tags=["messages"])
MESSAGE_QUEUE = "message_delivery"


class MessageCreate(BaseModel):
    run_id: UUID | None = None
    agent_id: UUID | None = None
    channel: str = Field(min_length=1)
    direction: str = Field(pattern="^(inbound|outbound|agent)$")
    body: str = Field(min_length=1)
    external_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RuntimeEventCreate(BaseModel):
    source: str = "openclaw"
    event_type: str = Field(min_length=1)
    channel: str = Field(min_length=1)
    direction: str = Field(pattern="^(inbound|outbound|agent)$")
    body: str = Field(min_length=1)
    run_id: UUID | None = None
    agent_id: UUID | None = None
    external_id: str | None = None
    delivery_state: str = "mirrored"
    metadata: dict[str, Any] = Field(default_factory=dict)


class Message(BaseModel):
    id: UUID
    run_id: UUID | None
    agent_id: UUID | None
    channel: str
    direction: str
    body: str
    delivery_state: str
    external_id: str | None
    metadata: dict[str, Any]
    created_at: str


class MessageRepository:
    def __init__(self, connection: Connection):
        self.connection = connection

    def list(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM messages ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
            return list(cursor.fetchall())

    def get(self, message_id: UUID) -> dict[str, Any] | None:
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT * FROM messages WHERE id = %s", (message_id,))
            return cursor.fetchone()

    def create(self, payload: MessageCreate) -> dict[str, Any]:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO messages (
                    run_id, agent_id, channel, direction, body, external_id,
                    metadata, delivery_state
                )
                VALUES (
                    %(run_id)s, %(agent_id)s, %(channel)s, %(direction)s,
                    %(body)s, %(external_id)s, %(metadata)s, 'queued'
                )
                RETURNING *
                """,
                {
                    **payload.model_dump(),
                    "metadata": Jsonb(payload.metadata),
                },
            )
            row = cursor.fetchone()
        self.connection.commit()
        return row

    def mirror_event(self, payload: RuntimeEventCreate) -> dict[str, Any]:
        if payload.external_id:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT *
                    FROM messages
                    WHERE channel = %s AND external_id = %s
                    """,
                    (payload.channel, payload.external_id),
                )
                existing = cursor.fetchone()
                if existing:
                    return existing

        metadata = {
            **payload.metadata,
            "source": payload.source,
            "event_type": payload.event_type,
        }
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO messages (
                    run_id, agent_id, channel, direction, body, external_id,
                    metadata, delivery_state
                )
                VALUES (
                    %(run_id)s, %(agent_id)s, %(channel)s, %(direction)s,
                    %(body)s, %(external_id)s, %(metadata)s, %(delivery_state)s
                )
                RETURNING *
                """,
                {
                    **payload.model_dump(),
                    "metadata": Jsonb(metadata),
                },
            )
            row = cursor.fetchone()
            cursor.execute(
                """
                INSERT INTO run_logs (run_id, level, message, metadata)
                VALUES (%s, 'info', 'runtime event mirrored', %s)
                """,
                (
                    payload.run_id,
                    Jsonb(
                        {
                            "message_id": str(row["id"]),
                            "source": payload.source,
                            "event_type": payload.event_type,
                            "channel": payload.channel,
                        }
                    ),
                ),
            )
        self.connection.commit()
        return row


class MessageBus:
    def __init__(self, redis: Redis):
        self.redis = redis

    def enqueue(self, message_id: UUID) -> None:
        self.redis.lpush(MESSAGE_QUEUE, str(message_id))


def get_message_repository(
    connection: Connection = Depends(get_connection),
) -> MessageRepository:
    return MessageRepository(connection)


def get_message_bus() -> MessageBus:
    return MessageBus(Redis.from_url(settings.redis_url))


def _serialize(row: dict[str, Any]) -> Message:
    payload = dict(row)
    payload["created_at"] = payload["created_at"].isoformat()
    return Message.model_validate(payload)


@router.get("", response_model=list[Message])
def list_messages(
    repository: MessageRepository = Depends(get_message_repository),
) -> list[Message]:
    return [_serialize(row) for row in repository.list()]


@router.post("", response_model=Message, status_code=status.HTTP_202_ACCEPTED)
def create_message(
    payload: MessageCreate,
    repository: MessageRepository = Depends(get_message_repository),
    bus: MessageBus = Depends(get_message_bus),
) -> Message:
    row = repository.create(payload)
    bus.enqueue(row["id"])
    return _serialize(row)


@router.post("/runtime-events", response_model=Message, status_code=status.HTTP_202_ACCEPTED)
def mirror_runtime_event(
    payload: RuntimeEventCreate,
    repository: MessageRepository = Depends(get_message_repository),
) -> Message:
    return _serialize(repository.mirror_event(payload))


@router.get("/{message_id}", response_model=Message)
def get_message(
    message_id: UUID,
    repository: MessageRepository = Depends(get_message_repository),
) -> Message:
    row = repository.get(message_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return _serialize(row)
