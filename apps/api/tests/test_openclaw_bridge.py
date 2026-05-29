import json
from datetime import UTC, datetime
from uuid import uuid4

from app.integrations import openclaw
from app.config import settings


def test_sync_agent_to_openclaw_writes_workspace_and_config(tmp_path, monkeypatch):
    config_path = tmp_path / "config" / "openclaw.json"
    workspace_root = tmp_path / "workspace"
    monkeypatch.setattr(settings, "openclaw_config_path", str(config_path))
    monkeypatch.setattr(settings, "openclaw_workspace_root", str(workspace_root))
    monkeypatch.setattr(settings, "openclaw_container_workspace_root", "/oc/workspace")
    monkeypatch.setattr(settings, "openclaw_container_agent_root", "/oc/agents")

    agent_id = uuid4()
    agent = {
        "id": agent_id,
        "name": "Research Lead",
        "role": "Researches requirements",
        "system_prompt": "Find facts before answering.",
        "model": "gpt-4.1-mini",
        "tools": ["web-search"],
        "channels": ["telegram"],
        "schedules": [{"kind": "manual"}],
        "memory": {"project": "agent-platform"},
        "skills": ["research"],
        "interaction_rules": ["cite sources"],
        "guardrails": ["no secrets"],
        "sync_status": "pending",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }

    result = openclaw.sync_agent_to_openclaw(agent)

    workspace = workspace_root / "app-agents" / str(agent_id)
    assert (workspace / "AGENTS.md").exists()
    assert (workspace / "SOUL.md").read_text().count("Find facts before answering.") == 1
    assert json.loads((workspace / "agent.json").read_text())["agent"]["id"] == str(agent_id)

    config = json.loads(config_path.read_text())
    openclaw_agent = config["agents"]["list"][0]
    assert openclaw_agent["id"] == result["openclaw_agent_id"]
    assert openclaw_agent["workspace"] == f"/oc/workspace/app-agents/{agent_id}"
    assert openclaw_agent["agentDir"].startswith("/oc/agents/")
    assert "lastTouchedBy" not in config.get("meta", {})
