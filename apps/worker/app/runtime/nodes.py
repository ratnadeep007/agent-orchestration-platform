import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import settings


def execute_node(
    node: dict[str, Any],
    upstream: dict[str, dict[str, Any]],
    agent: dict[str, Any] | None = None,
    trigger: dict[str, Any] | None = None,
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
        return execute_node_with_openai(node, upstream, agent, trigger)

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
) -> dict[str, Any]:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required when WORKFLOW_EXECUTION_MODE=openai")

    node_id = str(node["id"])
    label = str(node.get("label") or node_id)
    model = str(node.get("model") or (agent or {}).get("model") or settings.workflow_default_model)
    system_prompt = runtime_system_prompt(node, agent)
    user_prompt = runtime_user_prompt(node, upstream, trigger)
    response = openai_responses_create(model, system_prompt, user_prompt)

    return {
        "node_id": node_id,
        "label": label,
        "summary": normalize_node_reply(response["text"]),
        "runtime": "openai",
        "model": model,
        "usage": response.get("usage") or {},
        "upstream_count": len(upstream),
        "agent_id": str(agent["id"]) if agent else None,
        "openclaw_agent_id": agent.get("openclaw_agent_id") if agent else None,
        "openai_response_id": response.get("id"),
    }


def runtime_system_prompt(node: dict[str, Any], agent: dict[str, Any] | None) -> str:
    node_guidance = node_execution_guidance(node)
    if agent:
        return "\n".join(
            [
                str(agent["system_prompt"]),
                "",
                f"Role: {agent['role']}",
                f"OpenClaw agent id: {agent.get('openclaw_agent_id') or 'not synced'}",
                "Return exactly two sections in this order: Result, then Notes.",
                "Keep Result concrete and user-facing.",
                "Keep Notes short and clearly separated from the result.",
                "If the workflow was triggered by a user message, use that request as the primary task.",
                node_guidance,
            ]
        )

    return "\n".join(
        [
            f"You are executing workflow node {node.get('label') or node.get('id')}.",
            f"Role: {node.get('role') or 'workflow agent'}",
            "Return exactly two sections in this order: Result, then Notes.",
            "Keep Result concrete and user-facing.",
            "Keep Notes short and clearly separated from the result.",
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
            "Format:",
            "Result: <the direct answer or outcome first>",
            "Notes: <supporting notes, assumptions, or next-step template>",
        ]
    )


def format_node_reply(result: str, notes: str) -> str:
    return "\n\n".join(
        [
            f"**Result:**\n{result.strip()}",
            f"**Notes:**\n{notes.strip()}",
        ]
    )


def normalize_node_reply(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return stripped
    if "Result:" in stripped and ("Scaffolding:" in stripped or "Notes:" in stripped):
        return stripped

    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if not lines:
        return stripped

    first = lines[0]
    remainder = "\n".join(lines[1:]).strip()
    if remainder:
        return format_node_reply(first, remainder)
    return format_node_reply(first, "No additional notes provided.")


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
    return {"id": data.get("id"), "text": text, "usage": data.get("usage") or {}}


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
