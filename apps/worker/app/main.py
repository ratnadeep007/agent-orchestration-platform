import logging
import json
import time
from collections import deque
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID

from psycopg import connect
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from redis import Redis

from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("agent_platform.worker")
MESSAGE_QUEUE = "message_delivery"
WORKFLOW_RUN_QUEUE = "workflow_run_execution"


def main() -> None:
    redis = Redis.from_url(settings.redis_url)
    logger.info("worker started")

    while True:
        try:
            item = redis.brpop([WORKFLOW_RUN_QUEUE, MESSAGE_QUEUE], timeout=30)
            if item is None:
                logger.info("worker heartbeat")
                continue

            queue, raw_id = item
            queue_name = queue.decode("utf-8")
            if queue_name == WORKFLOW_RUN_QUEUE:
                execute_workflow_run(UUID(raw_id.decode("utf-8")))
            else:
                mark_message_delivered(UUID(raw_id.decode("utf-8")))
        except Exception:
            logger.exception("worker dependency check failed")

        time.sleep(1)


def execute_workflow_run(run_id: UUID) -> None:
    with connect(settings.database_url, row_factory=dict_row) as connection:
        run = _claim_run(connection, run_id)
        if run is None:
            logger.info("workflow run %s was already claimed or missing", run_id)
            return

        try:
            graph = _normalize_graph(run["graph_snapshot"])
            outputs: dict[str, dict[str, Any]] = {}
            _log(connection, run_id, "info", "workflow run started", {})

            for node in _execution_order(graph):
                node_id = str(node["id"])
                label = str(node.get("label") or node_id)
                upstream = _upstream_outputs(node_id, graph, outputs)
                output = _execute_node(node, upstream)
                outputs[node_id] = output

                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE workflow_run_nodes
                        SET
                            status = 'running',
                            input = %s,
                            started_at = COALESCE(started_at, now()),
                            updated_at = now()
                        WHERE run_id = %s AND node_id = %s
                        """,
                        (Jsonb({"upstream": upstream}), run_id, node_id),
                    )
                    cursor.execute(
                        """
                        UPDATE workflow_run_nodes
                        SET
                            status = 'succeeded',
                            output = %s,
                            completed_at = now(),
                            updated_at = now()
                        WHERE run_id = %s AND node_id = %s
                        """,
                        (Jsonb(output), run_id, node_id),
                    )
                    cursor.execute(
                        """
                        INSERT INTO messages (
                            run_id, channel, direction, body, delivery_state, metadata
                        )
                        VALUES (%s, 'workflow', 'agent', %s, 'persisted', %s)
                        """,
                        (
                            run_id,
                            f"{label} completed",
                            Jsonb({"node_id": node_id, "node_type": node.get("type", "agent")}),
                        ),
                    )
                _log(
                    connection,
                    run_id,
                    "info",
                    "workflow node completed",
                    {"node_id": node_id, "label": label},
                )

            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE workflow_runs
                    SET status = 'succeeded', completed_at = now(), updated_at = now()
                    WHERE id = %s
                    """,
                    (run_id,),
                )
            _log(connection, run_id, "info", "workflow run succeeded", {})
            connection.commit()
        except Exception as caught:
            connection.rollback()
            _fail_run(run_id, str(caught))
            raise


def mark_message_delivered(message_id: UUID) -> None:
    with connect(settings.database_url, row_factory=dict_row) as connection:
        message = _get_message(connection, message_id)
        if message is None:
            logger.info("message %s was missing", message_id)
            return

        if message["channel"] == "telegram" and message["direction"] == "outbound":
            try:
                telegram_response = _send_telegram_message(message)
                _mark_message_state(
                    connection,
                    message_id,
                    "delivered",
                    {"telegram_response": telegram_response},
                )
            except Exception as caught:
                _mark_message_state(connection, message_id, "failed", {"error": str(caught)})
                raise
            return

        _mark_message_state(connection, message_id, "delivered", {})


def _get_message(connection, message_id: UUID) -> dict[str, Any] | None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM messages WHERE id = %s", (message_id,))
        return cursor.fetchone()


def _mark_message_state(
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


def _send_telegram_message(message: dict[str, Any]) -> dict[str, Any]:
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


def _claim_run(connection, run_id: UUID) -> dict[str, Any] | None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE workflow_runs
            SET status = 'running', started_at = COALESCE(started_at, now()), updated_at = now()
            WHERE id = %s AND status = 'queued'
            RETURNING *
            """,
            (run_id,),
        )
        return cursor.fetchone()


def _fail_run(run_id: UUID, error: str) -> None:
    with connect(settings.database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE workflow_runs
                SET status = 'failed', error = %s, completed_at = now(), updated_at = now()
                WHERE id = %s
                """,
                (error, run_id),
            )
            cursor.execute(
                """
                INSERT INTO run_logs (run_id, level, message, metadata)
                VALUES (%s, 'error', 'workflow run failed', %s)
                """,
                (run_id, Jsonb({"error": error})),
            )
        connection.commit()


def _log(connection, run_id: UUID, level: str, message: str, metadata: dict[str, Any]) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO run_logs (run_id, level, message, metadata)
            VALUES (%s, %s, %s, %s)
            """,
            (run_id, level, message, Jsonb(metadata)),
        )


def _normalize_graph(graph: dict[str, Any]) -> dict[str, Any]:
    return {
        "nodes": graph["nodes"] if isinstance(graph.get("nodes"), list) else [],
        "edges": graph["edges"] if isinstance(graph.get("edges"), list) else [],
        "openclaw": graph["openclaw"] if isinstance(graph.get("openclaw"), dict) else {},
    }


def _execution_order(graph: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = [node for node in graph["nodes"] if "id" in node]
    node_ids = {str(node["id"]) for node in nodes}
    by_id = {str(node["id"]): node for node in nodes}
    dependencies: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    dependents: dict[str, set[str]] = {node_id: set() for node_id in node_ids}

    for edge in graph["edges"]:
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        if source in node_ids and target in node_ids and source != target:
            dependencies[target].add(source)
            dependents[source].add(target)

    ready = deque(node_id for node_id in by_id if not dependencies[node_id])
    ordered: list[str] = []
    while ready:
        node_id = ready.popleft()
        if node_id in ordered:
            continue
        ordered.append(node_id)
        for dependent in dependents[node_id]:
            dependencies[dependent].discard(node_id)
            if not dependencies[dependent]:
                ready.append(dependent)

    ordered.extend(node_id for node_id in by_id if node_id not in ordered)
    return [by_id[node_id] for node_id in ordered]


def _upstream_outputs(
    node_id: str,
    graph: dict[str, Any],
    outputs: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    upstream = {}
    for edge in graph["edges"]:
        if str(edge.get("target", "")) == node_id:
            source = str(edge.get("source", ""))
            if source in outputs:
                upstream[source] = outputs[source]
    return upstream


def _execute_node(node: dict[str, Any], upstream: dict[str, dict[str, Any]]) -> dict[str, Any]:
    node_id = str(node["id"])
    node_type = str(node.get("type", "agent"))
    label = str(node.get("label") or node_id)

    if node_type == "condition":
        return {
            "node_id": node_id,
            "label": label,
            "decision": "not_evaluated",
            "condition": node.get("condition", ""),
            "upstream_count": len(upstream),
        }

    return {
        "node_id": node_id,
        "label": label,
        "summary": f"{label} executed with {len(upstream)} upstream result(s).",
        "upstream_count": len(upstream),
    }


if __name__ == "__main__":
    main()
