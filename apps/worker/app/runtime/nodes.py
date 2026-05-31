import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import settings
from app.runtime.tools import execute_tool, openai_function_tools


def execute_node(
    node: dict[str, Any],
    upstream: dict[str, dict[str, Any]],
    agent: dict[str, Any] | None = None,
    trigger: dict[str, Any] | None = None,
    connection: Any | None = None,
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
        return execute_node_with_openai(node, upstream, agent, trigger, connection)

    result = f"{label} completed with {len(upstream)} upstream result(s)."
    notes = (
        f"Upstream count: {len(upstream)}.\n"
        "Continue only if more context is needed."
    )
    return {
        "node_id": node_id,
        "label": label,
        "summary": format_node_reply(result, notes),
        "upstream_count": len(upstream),
        "runtime": "mock",
        "agent_id": str(agent["id"]) if agent else None,
        "openclaw_agent_id": agent.get("openclaw_agent_id") if agent else None,
    }


def execute_node_with_openai(
    node: dict[str, Any],
    upstream: dict[str, dict[str, Any]],
    agent: dict[str, Any] | None,
    trigger: dict[str, Any] | None,
    connection: Any | None = None,
) -> dict[str, Any]:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required when WORKFLOW_EXECUTION_MODE=openai")

    node_id = str(node["id"])
    label = str(node.get("label") or node_id)
    model = str(node.get("model") or (agent or {}).get("model") or settings.workflow_default_model)
    system_prompt = runtime_system_prompt(node, agent)
    user_prompt = runtime_user_prompt(node, upstream, trigger)
    openai_tools = openai_function_tools(agent)
    response, usage, tool_calls = run_openai_tool_loop(
        model,
        system_prompt,
        user_prompt,
        openai_tools,
        trigger=trigger,
        connection=connection,
    )
    text = response.get("text") or extract_openai_text(response)
    if not text:
        raise RuntimeError("OpenAI response did not contain output text")

    return {
        "node_id": node_id,
        "label": label,
        "summary": normalize_node_reply(text),
        "runtime": "openai",
        "model": model,
        "usage": usage,
        "tool_calls": tool_calls,
        "upstream_count": len(upstream),
        "agent_id": str(agent["id"]) if agent else None,
        "openclaw_agent_id": agent.get("openclaw_agent_id") if agent else None,
        "openai_response_id": response.get("id"),
    }


def runtime_system_prompt(node: dict[str, Any], agent: dict[str, Any] | None) -> str:
    node_guidance = node_execution_guidance(node)
    if agent:
        selected_tools = ", ".join(agent.get("tools") or []) or "none"
        return "\n".join(
            [
                str(agent["system_prompt"]),
                "",
                f"Role: {agent['role']}",
                f"OpenClaw agent id: {agent.get('openclaw_agent_id') or 'not synced'}",
                f"Available tools: {selected_tools}",
                "Return only JSON that matches this schema: {\"result\": string, \"notes\": string}.",
                "Keep result concrete and user-facing.",
                "Keep notes short and clearly separated from the result.",
                "Do not use markdown, prose outside JSON, or nested Result/Notes labels.",
                "If the workflow was triggered by a user message, use that request as the primary task.",
                node_guidance,
            ]
        )

    return "\n".join(
        [
            f"You are executing workflow node {node.get('label') or node.get('id')}.",
            f"Role: {node.get('role') or 'workflow agent'}",
            "Return only JSON that matches this schema: {\"result\": string, \"notes\": string}.",
            "Keep result concrete and user-facing.",
            "Keep notes short and clearly separated from the result.",
            "Do not use markdown, prose outside JSON, or nested Result/Notes labels.",
            "If the workflow was triggered by a user message, use that request as the primary task.",
            node_guidance,
        ]
    )


def runtime_user_prompt(
    node: dict[str, Any],
    upstream: dict[str, dict[str, Any]],
    trigger: dict[str, Any] | None,
) -> str:
    trigger_payload = trigger or {}
    node_guidance = node_execution_guidance(node)
    return "\n".join(
        [
            "Execute this workflow node.",
            "",
            "Trigger:",
            json.dumps(trigger_payload, indent=2, sort_keys=True),
            "",
            "Node:",
            json.dumps(node, indent=2, sort_keys=True),
            "",
            "Upstream outputs:",
            json.dumps(upstream, indent=2, sort_keys=True),
            "",
            "Node guidance:",
            node_guidance,
            "",
            "Available tools will be executed by the worker when the model calls them.",
            "",
            "Format:",
            "{\"result\":\"<the direct answer or outcome first>\",\"notes\":\"<supporting notes, assumptions, or next-step context>\"}",
        ]
    )


def format_node_reply(result: str, notes: str) -> str:
    return "\n\n".join(
        [
            f"Result:\n{result.strip()}",
            f"Notes:\n{notes.strip()}",
        ]
    )


def normalize_node_reply(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return stripped

    json_reply = parse_json_reply(stripped)
    if json_reply:
        return format_node_reply(
            json_reply.get("result") or "No result provided.",
            json_reply.get("notes") or "No additional notes provided.",
        )

    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if not lines:
        return stripped

    first = lines[0]
    remainder = "\n".join(lines[1:]).strip()
    if remainder:
        return format_node_reply(first, remainder)
    return format_node_reply(first, "No additional notes provided.")


def parse_json_reply(text: str) -> dict[str, str] | None:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None

    result = payload.get("result")
    notes = payload.get("notes")
    if not isinstance(result, str) and not isinstance(notes, str):
        return None

    return {
        "result": result.strip() if isinstance(result, str) else "",
        "notes": notes.strip() if isinstance(notes, str) else "",
    }


def node_execution_guidance(node: dict[str, Any]) -> str:
    label = str(node.get("label") or node.get("id") or "").strip().lower()
    role = str(node.get("role") or "").strip().lower()
    text = " ".join(part for part in [label, role] if part)

    if any(term in text for term in ("research", "researcher", "fact", "triage", "specialist")):
        return (
            "This node must produce the concrete facts, classification, or investigation outcome "
            "for the user request. Do not draft the final reply or repeat upstream content verbatim."
        )

    if any(term in text for term in ("writer", "responder", "draft", "reply")):
        return (
            "This node must synthesize the upstream findings into a user-facing draft. "
            "Do not repeat the whole investigation; turn it into the reply the user should read."
        )

    if any(term in text for term in ("review", "reviewer", "approval", "approve", "check")):
        return (
            "This node must review the upstream output and return an evaluation or decision. "
            "Focus on whether the content is ready, what is missing, and what should change."
        )

    if "condition" in str(node.get("type", "")).lower():
        return "This node evaluates whether the workflow should continue or stop."

    return (
        "This node must contribute a distinct step in the workflow, building on upstream outputs "
        "without repeating them verbatim."
    )


def run_openai_tool_loop(
    model: str,
    system_prompt: str,
    user_prompt: str,
    tools: list[dict[str, Any]],
    *,
    trigger: dict[str, Any] | None,
    connection: Any | None,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    input_items: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    aggregate_usage: dict[str, Any] = {}
    tool_trace: list[dict[str, Any]] = []
    response: dict[str, Any] | None = None

    for _ in range(5):
        response = openai_responses_create(model, input_items, tools)
        aggregate_usage = merge_usage(aggregate_usage, response.get("usage") or {})
        output_items = response.get("output", [])
        input_items.extend(output_items)
        function_calls = [item for item in output_items if item.get("type") == "function_call"]
        if not function_calls:
            break

        for item in function_calls:
            arguments = parse_tool_arguments(item.get("arguments"))
            result = execute_tool(
                str(item.get("name") or ""),
                arguments,
                context={
                    "trigger": trigger or {},
                    "workflow_run_id": (trigger or {}).get("workflow_run_id"),
                    "connection": connection,
                },
            )
            tool_trace.append(
                {
                    "call_id": item.get("call_id"),
                    "name": item.get("name"),
                    "arguments": arguments,
                    "output": result,
                }
            )
            input_items.append(
                {
                    "type": "function_call_output",
                    "call_id": item["call_id"],
                    "output": json.dumps(result, ensure_ascii=False),
                }
            )
    if response is None:
        raise RuntimeError("OpenAI did not return a response")
    return response, aggregate_usage, tool_trace


def openai_responses_create(
    model: str,
    input_items: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "input": input_items,
        "max_output_tokens": 600,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "workflow_node_reply",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "result": {
                            "type": "string",
                            "description": "The direct user-facing answer or workflow outcome.",
                        },
                        "notes": {
                            "type": "string",
                            "description": "Short supporting context, assumptions, or next steps.",
                        },
                    },
                    "required": ["result", "notes"],
                    "additionalProperties": False,
                },
            }
        },
    }
    if tools:
        payload["tools"] = tools
    request = Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
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

    return {
        "id": data.get("id"),
        "text": extract_openai_text(data),
        "usage": data.get("usage") or {},
        "output": data.get("output") or [],
    }


def extract_openai_text(data: dict[str, Any]) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]

    parts: list[str] = []
    for output in data.get("output", []):
        for content in output.get("content", []):
            text = content.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts).strip()


def parse_tool_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, str) or not arguments.strip():
        return {}
    try:
        parsed = json.loads(arguments)
    except json.JSONDecodeError:
        return {"_raw": arguments}
    return parsed if isinstance(parsed, dict) else {"_raw": parsed}


def merge_usage(total: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    merged = dict(total)
    total_details = merged.get("input_tokens_details")
    if not isinstance(total_details, dict):
        total_details = {}
    current_details = current.get("input_tokens_details")
    if not isinstance(current_details, dict):
        current_details = {}
    merged["input_tokens"] = int(merged.get("input_tokens") or merged.get("prompt_tokens") or 0) + int(
        current.get("input_tokens") or current.get("prompt_tokens") or 0
    )
    merged["output_tokens"] = int(merged.get("output_tokens") or merged.get("completion_tokens") or 0) + int(
        current.get("output_tokens") or current.get("completion_tokens") or 0
    )
    merged["input_tokens_details"] = {
        "cached_tokens": int(total_details.get("cached_tokens") or 0)
        + int(current_details.get("cached_tokens") or 0)
    }
    return merged
