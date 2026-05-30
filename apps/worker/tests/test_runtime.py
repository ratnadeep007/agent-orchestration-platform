from app.runtime import nodes


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
