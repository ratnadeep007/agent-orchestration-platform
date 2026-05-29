import json
import logging
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID

from psycopg import connect
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.config import settings

logger = logging.getLogger("agent_platform.worker")


def mark_message_delivered(message_id: UUID) -> None:
    with connect(settings.database_url, row_factory=dict_row) as connection:
        message = get_message(connection, message_id)
        if message is None:
            logger.info("message %s was missing", message_id)
            return

        if message["channel"] == "telegram" and message["direction"] == "outbound":
            try:
                telegram_response = send_telegram_message(message)
                mark_message_state(
                    connection,
                    message_id,
                    "delivered",
                    {"telegram_response": telegram_response},
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


def send_telegram_message(message: dict[str, Any]) -> dict[str, Any]:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required for outbound Telegram delivery")

    chat_id = str(message["metadata"].get("chat_id", ""))
    if not chat_id:
        raise RuntimeError("metadata.chat_id is required for outbound Telegram delivery")

    if settings.telegram_allowed_chat_id and chat_id != settings.telegram_allowed_chat_id:
        raise RuntimeError("Telegram chat is not allowed")

    payload = json.dumps({"chat_id": chat_id, "text": message["body"]}).encode("utf-8")
    request = Request(
        f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as caught:
        body = caught.read().decode("utf-8")
        raise RuntimeError(f"Telegram send failed with HTTP {caught.code}: {body}") from caught
    except URLError as caught:
        raise RuntimeError(f"Telegram send failed: {caught.reason}") from caught
