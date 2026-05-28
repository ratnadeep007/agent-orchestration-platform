ALTER TABLE workflow_runs
ADD COLUMN IF NOT EXISTS graph_snapshot jsonb NOT NULL DEFAULT '{"nodes":[],"edges":[],"openclaw":{}}'::jsonb,
ADD COLUMN IF NOT EXISTS trigger jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS workflow_run_nodes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    node_id text NOT NULL,
    node_type text NOT NULL,
    label text NOT NULL,
    status text NOT NULL DEFAULT 'queued',
    input jsonb NOT NULL DEFAULT '{}'::jsonb,
    output jsonb NOT NULL DEFAULT '{}'::jsonb,
    error text,
    started_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (run_id, node_id)
);

CREATE INDEX IF NOT EXISTS idx_workflow_run_nodes_run_id ON workflow_run_nodes(run_id);
CREATE INDEX IF NOT EXISTS idx_workflow_run_nodes_status ON workflow_run_nodes(status);
