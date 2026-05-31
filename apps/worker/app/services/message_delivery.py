import logging
from typing import Any
from uuid import UUID

from psycopg import connect
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.config import settings
from app.channels.registry import deliver_message

logger = logging.getLogger("agent_platform.worker")


def mark_message_delivered(message_id: UUID) -> None:
    with connect(settings.database_url, row_factory=dict_row) as connection:
        message = get_message(connection, message_id)
        if message is None:
            logger.info("message %s was missing", message_id)
            return

        if message["direction"] == "outbound":
            try:
                delivery_response = deliver_message(message)
                mark_message_state(
                    connection,
                    message_id,
                    "delivered",
                    {"delivery_response": delivery_response},
                )
            except Exception as caught:
                mark_message_state(connection, message_id, "failed", {"error": str(caught)})
                raise
            return

        mark_message_state(connection, message_id, "delivered", {})


def get_message(connection, message_id: UUID) -> dict[str, Any] | None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM messages WHERE id = %s", (message_id,))
        return cursor.fetchone()


def mark_message_state(
    connection,
    message_id: UUID,
    delivery_state: str,
    metadata: dict[str, Any],
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE messages
            SET
                delivery_state = %s,
                metadata = metadata || %s
            WHERE id = %s
            """,
            (delivery_state, Jsonb(metadata), message_id),
        )
        cursor.execute(
            """
            INSERT INTO run_logs (run_id, level, message, metadata)
            SELECT run_id, %s, %s, jsonb_build_object('message_id', id::text, 'delivery_state', %s::text)
            FROM messages
            WHERE id = %s
            """,
            (
                "error" if delivery_state == "failed" else "info",
                "message delivery failed" if delivery_state == "failed" else "message delivered by worker",
                delivery_state,
                message_id,
            ),
        )
    connection.commit()
