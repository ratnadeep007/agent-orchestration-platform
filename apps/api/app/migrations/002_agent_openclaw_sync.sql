ALTER TABLE agents
    ADD COLUMN IF NOT EXISTS openclaw_agent_id text,
    ADD COLUMN IF NOT EXISTS openclaw_workspace_path text,
    ADD COLUMN IF NOT EXISTS last_synced_at timestamptz;

CREATE UNIQUE INDEX IF NOT EXISTS idx_agents_openclaw_agent_id
    ON agents(openclaw_agent_id)
    WHERE openclaw_agent_id IS NOT NULL;
