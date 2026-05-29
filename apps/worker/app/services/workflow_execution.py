import logging
from typing import Any
from uuid import UUID

from psycopg import connect
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.config import settings
from app.runtime.graph import execution_order, normalize_graph, upstream_outputs
from app.runtime.nodes import execute_node

logger = logging.getLogger("agent_platform.worker")


def execute_workflow_run(run_id: UUID) -> None:
    with connect(settings.database_url, row_factory=dict_row) as connection:
        run = claim_run(connection, run_id)
        if run is None:
            logger.info("workflow run %s was already claimed or missing", run_id)
            return

        try:
            graph = normalize_graph(run["graph_snapshot"])
            outputs: dict[str, dict[str, Any]] = {}
            log(connection, run_id, "info", "workflow run started", {})
            connection.commit()

            for node in execution_order(graph):
                node_id = str(node["id"])
                label = str(node.get("label") or node_id)
                upstream = upstream_outputs(node_id, graph, outputs)
                mark_node_running(connection, run_id, node_id, upstream)
                log(
                    connection,
                    run_id,
                    "info",
                    "workflow node started",
                    {"node_id": node_id, "label": label},
                )
                connection.commit()

                try:
                    agent = find_agent_for_node(connection, node)
                    output = execute_node(node, upstream, agent)
                except Exception as caught:
                    error = str(caught)
                    mark_node_failed(connection, run_id, node_id, error)
                    mark_run_failed(connection, run_id, error)
                    log(
                        connection,
                        run_id,
                        "error",
                        "workflow node failed",
                        {"node_id": node_id, "label": label, "error": error},
                    )
                    connection.commit()
                    raise

                outputs[node_id] = output
                mark_node_succeeded(connection, run_id, node, output, agent)
                log(
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

            mark_run_succeeded(connection, run_id)
            log(connection, run_id, "info", "workflow run succeeded", {})
            connection.commit()
        except Exception as caught:
            connection.rollback()
            fail_run_if_needed(run_id, str(caught))
            raise


def claim_run(connection, run_id: UUID) -> dict[str, Any] | None:
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


def mark_node_running(
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


def mark_node_succeeded(
    connection,
    run_id: UUID,
    node: dict[str, Any],
    output: dict[str, Any],
    agent: dict[str, Any] | None,
) -> None:
    node_id = str(node["id"])
    label = str(node.get("label") or node_id)
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


def mark_node_failed(connection, run_id: UUID, node_id: str, error: str) -> None:
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


def mark_run_succeeded(connection, run_id: UUID) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE workflow_runs
            SET status = 'succeeded', completed_at = now(), updated_at = now()
            WHERE id = %s
            """,
            (run_id,),
        )


def mark_run_failed(connection, run_id: UUID, error: str) -> None:
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


def fail_run_if_needed(run_id: UUID, error: str) -> None:
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


def log(connection, run_id: UUID, level: str, message: str, metadata: dict[str, Any]) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO run_logs (run_id, level, message, metadata)
            VALUES (%s, %s, %s, %s)
            """,
            (run_id, level, message, Jsonb(metadata)),
        )


def find_agent_for_node(connection, node: dict[str, Any]) -> dict[str, Any] | None:
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
