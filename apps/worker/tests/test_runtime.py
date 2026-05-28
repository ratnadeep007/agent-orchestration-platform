from app import main


def test_mock_node_execution_includes_agent_metadata():
    original_mode = main.settings.workflow_execution_mode
    main.settings.workflow_execution_mode = "mock"
    try:
        output = main._execute_node(
            {"id": "writer", "label": "Writer", "type": "agent"},
            {"researcher": {"summary": "facts"}},
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "openclaw_agent_id": "app-writer-abc",
            },
        )
    finally:
        main.settings.workflow_execution_mode = original_mode

    assert output["runtime"] == "mock"
    assert output["upstream_count"] == 1
    assert output["openclaw_agent_id"] == "app-writer-abc"


def test_openai_mode_requires_api_key():
    original_mode = main.settings.workflow_execution_mode
    original_key = main.settings.openai_api_key
    main.settings.workflow_execution_mode = "openai"
    main.settings.openai_api_key = ""
    try:
        try:
            main._execute_node({"id": "writer", "type": "agent"}, {}, None)
        except RuntimeError as caught:
            assert "OPENAI_API_KEY" in str(caught)
        else:
            raise AssertionError("expected RuntimeError")
    finally:
        main.settings.workflow_execution_mode = original_mode
        main.settings.openai_api_key = original_key


def test_extract_openai_output_text():
    assert (
        main._extract_openai_text(
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
