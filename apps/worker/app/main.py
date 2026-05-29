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
QUEUE_WAIT_SECONDS = 30
QUEUE_SOCKET_TIMEOUT_SECONDS = QUEUE_WAIT_SECONDS + 10


def main() -> None:
    redis = Redis.from_url(
        settings.redis_url,
        socket_connect_timeout=5,
        socket_timeout=QUEUE_SOCKET_TIMEOUT_SECONDS,
    )
    logger.info("worker started")

    while True:
        try:
            item = redis.brpop([WORKFLOW_RUN_QUEUE, MESSAGE_QUEUE], timeout=QUEUE_WAIT_SECONDS)
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
            connection.commit()

            for node in _execution_order(graph):
                node_id = str(node["id"])
                label = str(node.get("label") or node_id)
                upstream = _upstream_outputs(node_id, graph, outputs)
                _mark_node_running(connection, run_id, node_id, upstream)
                _log(
                    connection,
                    run_id,
                    "info",
                    "workflow node started",
                    {"node_id": node_id, "label": label},
                )
                connection.commit()

                try:
                    agent = _find_agent_for_node(connection, node)
                    output = _execute_node(node, upstream, agent)
                except Exception as caught:
                    error = str(caught)
                    _mark_node_failed(connection, run_id, node_id, error)
                    _mark_run_failed(connection, run_id, error)
                    _log(
                        connection,
                        run_id,
                        "error",
                        "workflow node failed",
                        {"node_id": node_id, "label": label, "error": error},
                    )
                    connection.commit()
                    raise

                outputs[node_id] = output

                with connection.cursor() as cursor:
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
                            Jsonb(
                                {
                                    "node_id": node_id,
                                    "node_type": node.get("type", "agent"),
                                    "runtime": output.get("runtime", "mock"),
                                    "agent_id": str(agent["id"]) if agent else None,
                                }
                            ),
                        ),
                    )
                _log(
                    connection,
                    run_id,
                    "info",
                    "workflow node completed",
                    {
                        "node_id": node_id,
                        "label": label,
                        "runtime": output.get("runtime", "mock"),
                    },
                )
                connection.commit()

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
            _fail_run_if_needed(run_id, str(caught))
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


def _mark_node_running(
    connection,
    run_id: UUID,
    node_id: str,
    upstream: dict[str, dict[str, Any]],
) -> None:
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


def _mark_node_failed(connection, run_id: UUID, node_id: str, error: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE workflow_run_nodes
            SET
                status = 'failed',
                error = %s,
                completed_at = now(),
                updated_at = now()
            WHERE run_id = %s AND node_id = %s
            """,
            (error, run_id, node_id),
        )


def _mark_run_failed(connection, run_id: UUID, error: str) -> None:
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


def _fail_run_if_needed(run_id: UUID, error: str) -> None:
    with connect(settings.database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE workflow_runs
                SET status = 'failed', error = %s, completed_at = now(), updated_at = now()
                WHERE id = %s AND status != 'failed'
                RETURNING id
                """,
                (error, run_id),
            )
            row = cursor.fetchone()
            if row is None:
                return
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


def _find_agent_for_node(connection, node: dict[str, Any]) -> dict[str, Any] | None:
    explicit_agent_id = node.get("agent_id") or node.get("agentId")
    with connection.cursor() as cursor:
        if explicit_agent_id:
            cursor.execute("SELECT * FROM agents WHERE id = %s", (explicit_agent_id,))
            return cursor.fetchone()

        candidates = {
            str(node.get("label", "")).strip().lower(),
            str(node.get("id", "")).strip().lower(),
        }
        candidates.discard("")
        if not candidates:
            return None
        cursor.execute(
            """
            SELECT *
            FROM agents
            WHERE lower(name) = ANY(%s)
            ORDER BY last_synced_at DESC NULLS LAST, updated_at DESC
            LIMIT 1
            """,
            (list(candidates),),
        )
        return cursor.fetchone()


def _execute_node(
    node: dict[str, Any],
    upstream: dict[str, dict[str, Any]],
    agent: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
            "runtime": "condition",
        }

    if settings.workflow_execution_mode == "openai":
        return _execute_node_with_openai(node, upstream, agent)

    return {
        "node_id": node_id,
        "label": label,
        "summary": f"{label} executed with {len(upstream)} upstream result(s).",
        "upstream_count": len(upstream),
        "runtime": "mock",
        "agent_id": str(agent["id"]) if agent else None,
        "openclaw_agent_id": agent.get("openclaw_agent_id") if agent else None,
    }


def _execute_node_with_openai(
    node: dict[str, Any],
    upstream: dict[str, dict[str, Any]],
    agent: dict[str, Any] | None,
) -> dict[str, Any]:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required when WORKFLOW_EXECUTION_MODE=openai")

    node_id = str(node["id"])
    label = str(node.get("label") or node_id)
    model = str(node.get("model") or (agent or {}).get("model") or settings.workflow_default_model)
    system_prompt = _runtime_system_prompt(node, agent)
    user_prompt = _runtime_user_prompt(node, upstream)
    response = _openai_responses_create(model, system_prompt, user_prompt)

    return {
        "node_id": node_id,
        "label": label,
        "summary": response["text"],
        "runtime": "openai",
        "model": model,
        "upstream_count": len(upstream),
        "agent_id": str(agent["id"]) if agent else None,
        "openclaw_agent_id": agent.get("openclaw_agent_id") if agent else None,
        "openai_response_id": response.get("id"),
    }


def _runtime_system_prompt(node: dict[str, Any], agent: dict[str, Any] | None) -> str:
    if agent:
        return "\n".join(
            [
                str(agent["system_prompt"]),
                "",
                f"Role: {agent['role']}",
                f"OpenClaw agent id: {agent.get('openclaw_agent_id') or 'not synced'}",
                "Return a concise workflow node result.",
            ]
        )

    return "\n".join(
        [
            f"You are executing workflow node {node.get('label') or node.get('id')}.",
            f"Role: {node.get('role') or 'workflow agent'}",
            "Return a concise workflow node result.",
        ]
    )


def _runtime_user_prompt(
    node: dict[str, Any],
    upstream: dict[str, dict[str, Any]],
) -> str:
    return "\n".join(
        [
            "Execute this workflow node.",
            "",
            "Node:",
            json.dumps(node, indent=2, sort_keys=True),
            "",
            "Upstream outputs:",
            json.dumps(upstream, indent=2, sort_keys=True),
        ]
    )


def _openai_responses_create(model: str, system_prompt: str, user_prompt: str) -> dict[str, Any]:
    payload = json.dumps(
        {
            "model": model,
            "input": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_output_tokens": 600,
        }
    ).encode("utf-8")
    request = Request(
        "https://api.openai.com/v1/responses",
        data=payload,
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as caught:
        body = caught.read().decode("utf-8")
        raise RuntimeError(f"OpenAI request failed with HTTP {caught.code}: {body}") from caught
    except URLError as caught:
        raise RuntimeError(f"OpenAI request failed: {caught.reason}") from caught

    text = _extract_openai_text(data)
    if not text:
        raise RuntimeError("OpenAI response did not contain output text")
    return {"id": data.get("id"), "text": text}


def _extract_openai_text(data: dict[str, Any]) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]

    parts: list[str] = []
    for output in data.get("output", []):
        for content in output.get("content", []):
            text = content.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts).strip()


if __name__ == "__main__":
    main()
