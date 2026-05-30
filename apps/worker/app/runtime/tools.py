from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from psycopg import connect
from psycopg.rows import dict_row

from app.config import settings

TOOL_CATALOG: dict[str, dict[str, Any]] = {
    "current_time": {
        "name": "current_time",
        "description": "Get the current server date and time in UTC.",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    "recent_messages": {
        "name": "recent_messages",
        "description": "Get the most recent messages for the active workflow run or chat.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 20,
                    "default": 5,
                    "description": "Maximum number of messages to return.",
                },
                "channel": {
                    "type": ["string", "null"],
                    "description": "Optional channel name filter such as telegram.",
                },
            },
            "required": ["limit", "channel"],
            "additionalProperties": False,
        },
    },
    "search_messages": {
        "name": "search_messages",
        "description": "Search message history for matching text within the active workflow run or chat.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "minLength": 1,
                    "description": "Search text to look for in message bodies.",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 20,
                    "default": 5,
                    "description": "Maximum number of matches to return.",
                },
                "channel": {
                    "type": ["string", "null"],
                    "description": "Optional channel name filter such as telegram.",
                },
            },
            "required": ["query", "limit", "channel"],
            "additionalProperties": False,
        },
    },
    "web_search": {
        "name": "web_search",
        "description": "Search the web via Firecrawl and return relevant results.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "minLength": 1,
                    "description": "Search text to look up on the web.",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 5,
                    "description": "Maximum number of results to return.",
                },
            },
            "required": ["query", "limit"],
            "additionalProperties": False,
        },
    },
}


def openai_function_tools(agent: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not agent:
        return []

    tools = []
    for name in agent.get("tools") or []:
        meta = TOOL_CATALOG.get(str(name))
        if not meta:
            continue
        tools.append(
            {
                "type": "function",
                "name": meta["name"],
                "description": meta["description"],
                "parameters": meta["parameters"],
                "strict": True,
            }
        )
    return tools


def execute_tool(
    name: str,
    arguments: dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if name == "current_time":
        return current_time_tool()
    if name == "recent_messages":
        return recent_messages_tool(arguments, context=context)
    if name == "search_messages":
        return search_messages_tool(arguments, context=context)
    if name == "web_search":
        return web_search_tool(arguments)
    return {
        "error": f"Unknown tool: {name}",
        "available_tools": sorted(TOOL_CATALOG.keys()),
    }


def current_time_tool() -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "iso": now.isoformat(),
        "date": now.date().isoformat(),
        "time": now.time().isoformat(timespec="seconds"),
        "timezone": "UTC",
    }


def recent_messages_tool(
    arguments: dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run_id = _workflow_run_id(context)
    if run_id is None:
        return {"error": "workflow_run_id is required"}

    limit = _bounded_limit(arguments.get("limit"), default=5)
    channel = _optional_text(arguments.get("channel"))
    where, params = _message_filters(run_id, channel, None)

    query = (
        "SELECT id, run_id, agent_id, channel, direction, body, created_at "
        "FROM messages "
        f"WHERE {where} "
        "ORDER BY created_at DESC "
        "LIMIT %s"
    )
    params.append(limit)
    rows = _query_messages(query, params, context=context)
    return {
        "run_id": str(run_id),
        "count": len(rows),
        "messages": rows,
    }


def search_messages_tool(
    arguments: dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run_id = _workflow_run_id(context)
    if run_id is None:
        return {"error": "workflow_run_id is required"}

    query_text = _optional_text(arguments.get("query"))
    if not query_text:
        return {"error": "query is required"}

    limit = _bounded_limit(arguments.get("limit"), default=5)
    channel = _optional_text(arguments.get("channel"))
    where, params = _message_filters(run_id, channel, query_text)

    query = (
        "SELECT id, run_id, agent_id, channel, direction, body, created_at "
        "FROM messages "
        f"WHERE {where} "
        "ORDER BY created_at DESC "
        "LIMIT %s"
    )
    params.append(limit)
    rows = _query_messages(query, params, context=context)
    return {
        "run_id": str(run_id),
        "query": query_text,
        "count": len(rows),
        "messages": rows,
    }


def web_search_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    query = _optional_text(arguments.get("query"))
    if not query:
        return {"error": "query is required"}

    limit = _bounded_limit(arguments.get("limit"), default=5, maximum=10)
    if not settings.firecrawl_api_key:
        return {"error": "FIRECRAWL_API_KEY is required for web_search"}

    payload = {
        "query": query,
        "limit": limit,
        "sources": ["web"],
        "scrapeOptions": {
            "formats": [{"type": "markdown"}],
            "onlyMainContent": True,
        },
    }
    request = Request(
        "https://api.firecrawl.dev/v2/search",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.firecrawl_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as caught:
        body = caught.read().decode("utf-8", errors="replace")
        return {"error": f"Firecrawl search failed with HTTP {caught.code}", "details": body[:500]}
    except URLError as caught:
        return {"error": f"Firecrawl search failed: {caught.reason}"}

    if not data.get("success"):
        return {
            "error": "Firecrawl search failed",
            "details": data.get("warning") or data.get("error") or "unknown error",
        }

    results = parse_firecrawl_results(data, limit=limit)
    return {
        "query": query,
        "count": len(results),
        "source": "firecrawl",
        "credits_used": data.get("creditsUsed"),
        "search_id": data.get("id"),
        "results": results,
    }


def _query_messages(
    query: str,
    params: list[Any],
    *,
    context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    existing_connection = (context or {}).get("connection")
    if existing_connection is not None:
        with existing_connection.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
    else:
        with connect(settings.database_url, row_factory=dict_row) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()
    return [
        {
            "id": str(row["id"]),
            "run_id": str(row["run_id"]) if row["run_id"] else None,
            "agent_id": str(row["agent_id"]) if row["agent_id"] else None,
            "channel": row["channel"],
            "direction": row["direction"],
            "body": row["body"],
            "created_at": row["created_at"].isoformat(),
        }
        for row in rows
    ]


def _message_filters(
    run_id: UUID,
    channel: str | None,
    query_text: str | None,
) -> tuple[str, list[Any]]:
    conditions = ["run_id = %s"]
    params: list[Any] = [run_id]
    if channel:
        conditions.append("channel = %s")
        params.append(channel)
    if query_text:
        conditions.append("body ILIKE %s")
        params.append(f"%{query_text}%")
    return " AND ".join(conditions), params


def _workflow_run_id(context: dict[str, Any] | None) -> UUID | None:
    if not context:
        return None
    value = context.get("workflow_run_id")
    if not value:
        return None
    return UUID(str(value))


def _bounded_limit(value: Any, *, default: int, maximum: int = 20) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(parsed, maximum))


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_firecrawl_results(data: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
    web_results = data.get("data", {}).get("web", [])
    results: list[dict[str, Any]] = []
    for item in web_results[:limit]:
        markdown = item.get("markdown")
        if isinstance(markdown, str):
            markdown = markdown.strip()
        results.append(
            {
                "title": item.get("title"),
                "description": item.get("description"),
                "url": item.get("url"),
                "markdown": markdown[:2000] if markdown else None,
                "metadata": item.get("metadata") or {},
            }
        )
    return results
