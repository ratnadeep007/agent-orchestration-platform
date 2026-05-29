import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import settings


def execute_node(
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
        return execute_node_with_openai(node, upstream, agent)

    return {
        "node_id": node_id,
        "label": label,
        "summary": f"{label} executed with {len(upstream)} upstream result(s).",
        "upstream_count": len(upstream),
        "runtime": "mock",
        "agent_id": str(agent["id"]) if agent else None,
        "openclaw_agent_id": agent.get("openclaw_agent_id") if agent else None,
    }


def execute_node_with_openai(
    node: dict[str, Any],
    upstream: dict[str, dict[str, Any]],
    agent: dict[str, Any] | None,
) -> dict[str, Any]:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required when WORKFLOW_EXECUTION_MODE=openai")

    node_id = str(node["id"])
    label = str(node.get("label") or node_id)
    model = str(node.get("model") or (agent or {}).get("model") or settings.workflow_default_model)
    system_prompt = runtime_system_prompt(node, agent)
    user_prompt = runtime_user_prompt(node, upstream)
    response = openai_responses_create(model, system_prompt, user_prompt)

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


def runtime_system_prompt(node: dict[str, Any], agent: dict[str, Any] | None) -> str:
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


def runtime_user_prompt(
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


def openai_responses_create(model: str, system_prompt: str, user_prompt: str) -> dict[str, Any]:
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

    text = extract_openai_text(data)
    if not text:
        raise RuntimeError("OpenAI response did not contain output text")
    return {"id": data.get("id"), "text": text}


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
