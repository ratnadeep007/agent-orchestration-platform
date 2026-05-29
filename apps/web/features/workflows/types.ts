export type WorkflowGraph = {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  openclaw: Record<string, unknown>;
};

export type WorkflowNode = {
  id: string;
  type: string;
  label?: string;
  role?: string;
  condition?: string;
  position?: { x: number; y: number };
};

export type WorkflowEdge = {
  id: string;
  source: string;
  target: string;
  label?: string;
  condition?: string;
};

export type WorkflowPayload = {
  name: string;
  description: string;
  graph: WorkflowGraph;
  status: string;
};

export type Workflow = WorkflowPayload & {
  id: string;
  created_at: string;
  updated_at: string;
};

export type WorkflowTemplate = {
  id: string;
  name: string;
  description: string;
  graph: WorkflowGraph;
  created_at: string;
};

export type WorkflowRunNode = {
  id: string;
  node_id: string;
  node_type: string;
  label: string;
  status: string;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
};

export type WorkflowRunLog = {
  id: string;
  level: string;
  message: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type WorkflowRun = {
  id: string;
  workflow_id: string | null;
  status: string;
  trigger: Record<string, unknown>;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
  nodes: WorkflowRunNode[];
  logs: WorkflowRunLog[];
};

export type FlowNodeData = {
  condition?: string;
  generated?: boolean;
  label: string;
  nodeType: string;
  role?: string;
  selected?: boolean;
  status?: string;
};
