from typing import Any
from uuid import UUID

from fastapi import Depends
from psycopg import Connection
from psycopg.types.json import Jsonb

from app.db import get_connection
from app.models.message import MessageCreate, RuntimeEventCreate


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

    def create_outbound(
        self,
        *,
        channel: str,
        body: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO messages (channel, direction, body, metadata, delivery_state)
                VALUES (%s, 'outbound', %s, %s, 'queued')
                RETURNING *
                """,
                (channel, body, Jsonb(metadata)),
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


def get_message_repository(
    connection: Connection = Depends(get_connection),
) -> MessageRepository:
    return MessageRepository(connection)
