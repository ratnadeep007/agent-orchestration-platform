import json

from app.runtime import nodes
from app.runtime import tools


def test_mock_node_execution_includes_agent_metadata():
    original_mode = nodes.settings.workflow_execution_mode
    nodes.settings.workflow_execution_mode = "mock"
    try:
        output = nodes.execute_node(
            {"id": "writer", "label": "Writer", "type": "agent"},
            {"researcher": {"summary": "facts"}},
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "openclaw_agent_id": "app-writer-abc",
            },
        )
    finally:
        nodes.settings.workflow_execution_mode = original_mode

    assert output["runtime"] == "mock"
    assert output["upstream_count"] == 1
    assert output["openclaw_agent_id"] == "app-writer-abc"
    assert output["summary"].startswith("**Result:**")
    assert "**Notes:**" in output["summary"]


def test_openai_mode_requires_api_key():
    original_mode = nodes.settings.workflow_execution_mode
    original_key = nodes.settings.openai_api_key
    nodes.settings.workflow_execution_mode = "openai"
    nodes.settings.openai_api_key = ""
    try:
        try:
            nodes.execute_node({"id": "writer", "type": "agent"}, {}, None)
        except RuntimeError as caught:
            assert "OPENAI_API_KEY" in str(caught)
        else:
            raise AssertionError("expected RuntimeError")
    finally:
        nodes.settings.workflow_execution_mode = original_mode
        nodes.settings.openai_api_key = original_key


def test_extract_openai_output_text():
    assert (
        nodes.extract_openai_text(
            {
                "output": [
                    {
                        "content": [
                            {"type": "output_text", "text": "node completed"},
                        ]
                    }
                ]
            }
        )
        == "node completed"
    )


def test_runtime_user_prompt_includes_trigger_context():
    prompt = nodes.runtime_user_prompt(
        {"id": "researcher", "label": "Researcher"},
        {},
        {"text": "/research summarize battery recycling", "telegram_command": "research"},
    )

    assert "\"telegram_command\": \"research\"" in prompt
    assert "\"text\": \"/research summarize battery recycling\"" in prompt


def test_execute_node_with_openai_preserves_usage_payload(monkeypatch):
    original_mode = nodes.settings.workflow_execution_mode
    original_key = nodes.settings.openai_api_key
    nodes.settings.workflow_execution_mode = "openai"
    nodes.settings.openai_api_key = "test-key"
    monkeypatch.setattr(
        nodes,
        "openai_responses_create",
        lambda model, input_items, tools=None: {
            "id": "resp_123",
            "text": "Result: done\nNotes: ok",
            "usage": {"input_tokens": 100, "output_tokens": 40},
            "output": [],
        },
    )
    try:
        output = nodes.execute_node_with_openai(
            {"id": "writer", "label": "Writer", "type": "agent"},
            {"researcher": {"summary": "facts"}},
            {
                "id": "agent-1",
                "role": "Writer",
                "system_prompt": "You draft replies.",
                "openclaw_agent_id": "app-writer",
            },
            {"text": "/research summarize battery recycling"},
        )
    finally:
        nodes.settings.workflow_execution_mode = original_mode
        nodes.settings.openai_api_key = original_key

    assert output["runtime"] == "openai"
    assert output["usage"] == {
        "input_tokens": 100,
        "output_tokens": 40,
        "input_tokens_details": {"cached_tokens": 0},
    }
    assert output["openai_response_id"] == "resp_123"
    assert output["tool_calls"] == []


def test_execute_node_with_openai_executes_tool_calls(monkeypatch):
    original_mode = nodes.settings.workflow_execution_mode
    original_key = nodes.settings.openai_api_key
    nodes.settings.workflow_execution_mode = "openai"
    nodes.settings.openai_api_key = "test-key"

    responses = iter(
        [
            {
                "id": "resp_1",
                "text": "",
                "usage": {"input_tokens": 10, "output_tokens": 1},
                "output": [
                    {
                        "type": "function_call",
                        "call_id": "call_1",
                        "name": "recent_messages",
                        "arguments": "{\"limit\": 2}",
                    }
                ],
            },
            {
                "id": "resp_2",
                "text": "Result: done\nNotes: tool used",
                "usage": {"input_tokens": 12, "output_tokens": 4},
                "output": [],
            },
        ]
    )
    seen_calls = []

    monkeypatch.setattr(
        nodes,
        "openai_responses_create",
        lambda model, input_items, tools=None: next(responses),
    )
    monkeypatch.setattr(
        nodes,
        "execute_tool",
        lambda name, arguments, context=None: seen_calls.append(
            {
                "name": name,
                "arguments": arguments,
                "workflow_run_id": context["workflow_run_id"],
            }
        )
        or {"ok": True, "tool": name},
    )

    try:
        output = nodes.execute_node_with_openai(
            {"id": "writer", "label": "Writer", "type": "agent"},
            {"researcher": {"summary": "facts"}},
            {
                "id": "agent-1",
                "role": "Writer",
                "system_prompt": "You draft replies.",
                "openclaw_agent_id": "app-writer",
                "tools": ["recent_messages"],
            },
            {"text": "/research summarize battery recycling", "workflow_run_id": "run-123"},
        )
    finally:
        nodes.settings.workflow_execution_mode = original_mode
        nodes.settings.openai_api_key = original_key

    assert output["runtime"] == "openai"
    assert output["usage"]["input_tokens"] == 22
    assert output["usage"]["output_tokens"] == 5
    assert output["tool_calls"][0]["name"] == "recent_messages"
    assert output["summary"].startswith("**Result:**")
    assert seen_calls == [
        {
            "name": "recent_messages",
            "arguments": {"limit": 2},
            "workflow_run_id": "run-123",
        }
    ]


def test_preferred_reply_node_is_marked_reply_node():
    from app.services.workflow_execution import preferred_reply_node_id

    assert (
        preferred_reply_node_id(
            {
                "graph_snapshot": {
                    "nodes": [
                        {"id": "researcher"},
                        {"id": "writer", "reply": True},
                        {"id": "reviewer"},
                    ]
                }
            }
        )
        == "writer"
    )


def test_estimate_openai_cost_uses_token_rates():
    from app.services.workflow_execution import estimate_openai_cost

    cost = estimate_openai_cost(
        "gpt-4o-mini",
        {
            "input_tokens": 1000,
            "output_tokens": 2000,
            "input_tokens_details": {"cached_tokens": 250},
        },
    )

    assert cost == 0.001331


def test_web_search_tool_parses_firecrawl_results(monkeypatch):
    original_key = tools.settings.firecrawl_api_key
    tools.settings.firecrawl_api_key = "test-key"
    sample_payload = {
        "success": True,
        "creditsUsed": 2,
        "id": "search_123",
        "data": {
            "web": [
                {
                    "title": "First Result",
                    "description": "First description",
                    "url": "https://example.com/one",
                    "markdown": "# First Result\nFirst markdown",
                    "metadata": {"sourceURL": "https://example.com/one"},
                },
                {
                    "title": "Second Result",
                    "description": "Second description",
                    "url": "https://example.com/two",
                    "markdown": "# Second Result\nSecond markdown",
                    "metadata": {"sourceURL": "https://example.com/two"},
                },
            ]
        },
    }

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(sample_payload).encode("utf-8")

    monkeypatch.setattr(tools, "urlopen", lambda request, timeout=0: Response())

    try:
        output = tools.execute_tool("web_search", {"query": "battery recycling", "limit": 2})
    finally:
        tools.settings.firecrawl_api_key = original_key

    assert output["source"] == "firecrawl"
    assert output["count"] == 2
    assert output["results"][0]["title"] == "First Result"
    assert output["results"][0]["url"] == "https://example.com/one"
    assert output["results"][0]["description"] == "First description"
    assert output["credits_used"] == 2
    assert output["search_id"] == "search_123"


def test_execute_tool_routes_web_search(monkeypatch):
    original_key = tools.settings.firecrawl_api_key
    tools.settings.firecrawl_api_key = "test-key"
    monkeypatch.setattr(
        tools,
        "web_search_tool",
        lambda arguments: {"query": arguments["query"], "count": 1},
    )

    try:
        assert tools.execute_tool("web_search", {"query": "openclaw"}) == {
            "query": "openclaw",
            "count": 1,
        }
    finally:
        tools.settings.firecrawl_api_key = original_key


def test_openai_function_tools_use_strict_required_properties():
    schema = tools.openai_function_tools(
        {
            "tools": ["recent_messages", "search_messages", "web_search"],
        }
    )

    assert schema[0]["parameters"]["required"] == ["limit", "channel"]
    assert schema[1]["parameters"]["required"] == ["query", "limit", "channel"]
    assert schema[2]["parameters"]["required"] == ["query", "limit"]
