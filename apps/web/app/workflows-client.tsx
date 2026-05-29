"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import type React from "react";
import { Clock3, GitBranch, Loader2, Play, Plus, RefreshCcw, Save, Trash2 } from "lucide-react";
import {
  Background,
  Controls,
  Handle,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

type WorkflowGraph = {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  openclaw: Record<string, unknown>;
};

type WorkflowNode = {
  id: string;
  type: string;
  label?: string;
  role?: string;
  condition?: string;
  position?: { x: number; y: number };
};

type WorkflowEdge = {
  id: string;
  source: string;
  target: string;
  label?: string;
  condition?: string;
};

type WorkflowPayload = {
  name: string;
  description: string;
  graph: WorkflowGraph;
  status: string;
};

type Workflow = WorkflowPayload & {
  id: string;
  created_at: string;
  updated_at: string;
};

type WorkflowTemplate = {
  id: string;
  name: string;
  description: string;
  graph: WorkflowGraph;
  created_at: string;
};

type WorkflowRunNode = {
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

type WorkflowRunLog = {
  id: string;
  level: string;
  message: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

type WorkflowRun = {
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

type FlowNodeData = {
  condition?: string;
  generated?: boolean;
  label: string;
  nodeType: string;
  role?: string;
  selected?: boolean;
  status?: string;
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const nodeTypes = { workflow: WorkflowFlowNode };

const emptyGraph: WorkflowGraph = {
  nodes: [
    {
      id: "orchestrator",
      label: "Orchestrator",
      role: "Route work to delegates",
      type: "agent",
      position: { x: 80, y: 120 },
    },
    {
      id: "delegate",
      label: "Delegate",
      role: "Complete assigned work",
      type: "agent",
      position: { x: 360, y: 120 },
    },
    {
      id: "review",
      condition: "needs_revision == true",
      label: "Review",
      type: "condition",
      position: { x: 640, y: 120 },
    },
  ],
  edges: [
    { id: "e1", source: "orchestrator", target: "delegate", label: "assign" },
    { id: "e2", source: "delegate", target: "review", label: "result" },
    {
      id: "e3",
      source: "review",
      target: "delegate",
      label: "feedback loop",
      condition: "needs revision",
    },
  ],
  openclaw: {
    delegates: ["delegate"],
    orchestrator: "orchestrator",
    strategy: "orchestrator-delegates",
  },
};

const emptyWorkflow: WorkflowPayload = {
  description: "",
  graph: emptyGraph,
  name: "",
  status: "draft",
};

export function WorkflowsClient() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedGraphNodeId, setSelectedGraphNodeId] = useState<string | null>(null);
  const [form, setForm] = useState<WorkflowPayload>(emptyWorkflow);
  const [graphText, setGraphText] = useState(JSON.stringify(emptyGraph, null, 2));
  const [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedWorkflow = useMemo(
    () => workflows.find((workflow) => workflow.id === selectedId) ?? null,
    [selectedId, workflows],
  );

  useEffect(() => {
    void loadAll();
  }, []);

  async function loadAll() {
    setLoading(true);
    setError(null);
    try {
      const [workflowResponse, templateResponse] = await Promise.all([
        fetch(`${apiUrl}/workflows`, { cache: "no-store" }),
        fetch(`${apiUrl}/workflows/templates`, { cache: "no-store" }),
      ]);
      if (!workflowResponse.ok || !templateResponse.ok) {
        throw new Error("Workflow load failed");
      }
      setWorkflows(await workflowResponse.json());
      setTemplates(await templateResponse.json());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Workflow load failed");
    } finally {
      setLoading(false);
    }
  }

  function selectWorkflow(workflow: Workflow) {
    setSelectedId(workflow.id);
    setForm({
      description: workflow.description,
      graph: workflow.graph,
      name: workflow.name,
      status: workflow.status,
    });
    setGraphText(JSON.stringify(workflow.graph, null, 2));
    setSelectedGraphNodeId(workflow.graph.nodes[0]?.id ?? null);
    void loadRuns(workflow.id);
  }

  function resetForm() {
    setSelectedId(null);
    setForm(emptyWorkflow);
    setGraphText(JSON.stringify(emptyGraph, null, 2));
    setSelectedGraphNodeId(emptyGraph.nodes[0]?.id ?? null);
    setRuns([]);
    setError(null);
  }

  function updateGraphFromBuilder(updater: (graph: WorkflowGraph) => WorkflowGraph) {
    try {
      const current = WorkflowGraphSchema(JSON.parse(graphText));
      const next = WorkflowGraphSchema(updater(current));
      setForm((currentForm) => ({ ...currentForm, graph: next }));
      setGraphText(JSON.stringify(next, null, 2));
      setError(null);
      return next;
    } catch {
      setError("Fix Graph JSON before using builder controls.");
      return null;
    }
  }

  function updateGraphNode(nodeId: string, patch: Partial<WorkflowNode>) {
    updateGraphFromBuilder((graph) => ({
      ...graph,
      nodes: graph.nodes.map((node) =>
        node.id === nodeId ? { ...node, ...patch } : node,
      ),
    }));
  }

  function addGraphNode(type: "agent" | "condition") {
    const next = updateGraphFromBuilder((graph) => {
      const nodeNumber = graph.nodes.length + 1;
      const id = uniqueGraphId(graph, type === "agent" ? "agent" : "condition");
      const lastPosition = graph.nodes.at(-1)?.position ?? { x: 80, y: 120 };
      const node: WorkflowNode = {
        id,
        label: type === "agent" ? `Agent ${nodeNumber}` : `Condition ${nodeNumber}`,
        position: { x: lastPosition.x + 280, y: lastPosition.y },
        type,
      };
      if (type === "agent") {
        node.role = "Describe this agent's responsibility";
      } else {
        node.condition = "status == true";
      }

      return {
        ...graph,
        nodes: [...graph.nodes, node],
      };
    });
    setSelectedGraphNodeId(next?.nodes.at(-1)?.id ?? null);
  }

  function removeGraphNode(nodeId: string) {
    const next = updateGraphFromBuilder((graph) => ({
      ...graph,
      edges: graph.edges.filter(
        (edge) => edge.source !== nodeId && edge.target !== nodeId,
      ),
      nodes: graph.nodes.filter((node) => node.id !== nodeId),
    }));
    setSelectedGraphNodeId(next?.nodes[0]?.id ?? null);
  }

  function addGraphEdge() {
    updateGraphFromBuilder((graph) => {
      if (graph.nodes.length < 2) {
        return graph;
      }
      const source = selectedGraphNodeId ?? graph.nodes[0].id;
      const sourceIndex = graph.nodes.findIndex((node) => node.id === source);
      const target = graph.nodes[sourceIndex + 1]?.id ?? graph.nodes[0].id;
      return {
        ...graph,
        edges: [
          ...graph.edges,
          {
            id: uniqueGraphId(graph, "edge"),
            label: "next",
            source,
            target,
          },
        ],
      };
    });
  }

  function updateGraphEdge(edgeId: string, patch: Partial<WorkflowEdge>) {
    updateGraphFromBuilder((graph) => ({
      ...graph,
      edges: graph.edges.map((edge) =>
        edge.id === edgeId ? { ...edge, ...patch } : edge,
      ),
    }));
  }

  function removeGraphEdge(edgeId: string) {
    updateGraphFromBuilder((graph) => ({
      ...graph,
      edges: graph.edges.filter((edge) => edge.id !== edgeId),
    }));
  }

  async function loadRuns(workflowId = selectedId) {
    if (!workflowId) {
      setRuns([]);
      return;
    }
    try {
      const response = await fetch(`${apiUrl}/workflows/${workflowId}/runs`, {
        cache: "no-store",
      });
      if (!response.ok) {
        throw new Error(`Run load failed: ${response.status}`);
      }
      const loadedRuns: WorkflowRun[] = await response.json();
      setRuns(loadedRuns);
      setSelectedRunId((current) => {
        if (current && loadedRuns.some((run) => run.id === current)) {
          return current;
        }
        return loadedRuns[0]?.id ?? null;
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Run load failed");
    }
  }

  async function instantiateTemplate(templateId: string) {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${apiUrl}/workflows/templates/${templateId}/instantiate`,
        { method: "POST" },
      );
      if (!response.ok) {
        throw new Error(`Template load failed: ${response.status}`);
      }
      const workflow = await response.json();
      await loadAll();
      selectWorkflow(workflow);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Template load failed");
    } finally {
      setLoading(false);
    }
  }

  async function saveWorkflow(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const graph = JSON.parse(graphText);
      const payload = { ...form, graph };
      const response = await fetch(
        selectedId ? `${apiUrl}/workflows/${selectedId}` : `${apiUrl}/workflows`,
        {
          body: JSON.stringify(payload),
          headers: { "Content-Type": "application/json" },
          method: selectedId ? "PUT" : "POST",
        },
      );
      if (!response.ok) {
        throw new Error(`Workflow save failed: ${response.status}`);
      }
      const saved = await response.json();
      await loadAll();
      selectWorkflow(saved);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Workflow save failed");
    } finally {
      setLoading(false);
    }
  }

  async function deleteWorkflow() {
    if (!selectedId) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiUrl}/workflows/${selectedId}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        throw new Error(`Workflow delete failed: ${response.status}`);
      }
      resetForm();
      await loadAll();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Workflow delete failed");
    } finally {
      setLoading(false);
    }
  }

  async function startRun() {
    if (!selectedId) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiUrl}/workflows/${selectedId}/runs`, {
        body: JSON.stringify({ trigger: { source: "web" } }),
        headers: { "Content-Type": "application/json" },
        method: "POST",
      });
      if (!response.ok) {
        throw new Error(`Workflow run failed: ${response.status}`);
      }
      const run: WorkflowRun = await response.json();
      setSelectedRunId(run.id);
      await loadRuns(selectedId);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Workflow run failed");
    } finally {
      setLoading(false);
    }
  }

  const previewGraph = useMemo(() => {
    try {
      return WorkflowGraphSchema(JSON.parse(graphText));
    } catch {
      return form.graph;
    }
  }, [form.graph, graphText]);

  const selectedRun = useMemo(
    () => runs.find((run) => run.id === selectedRunId) ?? runs[0] ?? null,
    [runs, selectedRunId],
  );

  return (
    <div className="grid min-w-0 gap-5 xl:grid-cols-[280px_minmax(0,1fr)]">
      <aside className="min-w-0 rounded-lg border border-slate-200 bg-white">
        <div className="flex items-center justify-between border-b border-slate-200 p-4">
          <div>
            <h2 className="text-sm font-semibold">Workflows</h2>
            <p className="text-xs text-slate-500">{workflows.length} saved</p>
          </div>
          <Button onClick={() => void loadAll()} size="sm" type="button" variant="outline">
            <RefreshCcw className="size-4" />
          </Button>
        </div>

        <div className="border-b border-slate-200 p-3">
          <p className="mb-2 text-xs font-medium text-slate-500">Templates</p>
          <div className="grid gap-2">
            {templates.map((template) => (
              <Button
                className="justify-start"
                key={template.id}
                onClick={() => void instantiateTemplate(template.id)}
                type="button"
                variant="outline"
              >
                <Plus className="mr-2 size-4" />
                {template.name}
              </Button>
            ))}
          </div>
        </div>

        <div className="max-h-[420px] overflow-auto p-2">
          {workflows.map((workflow) => (
            <button
              className={`flex w-full items-start gap-3 rounded-md p-3 text-left text-sm hover:bg-slate-50 ${
                selectedId === workflow.id ? "bg-slate-100" : ""
              }`}
              key={workflow.id}
              onClick={() => selectWorkflow(workflow)}
              type="button"
            >
              <GitBranch className="mt-0.5 size-4 shrink-0 text-slate-500" />
              <span>
                <span className="block font-medium">{workflow.name}</span>
                <span className="block text-xs text-slate-500">
                  {workflow.graph.nodes.length} nodes · {workflow.graph.edges.length} edges
                </span>
              </span>
            </button>
          ))}
        </div>
      </aside>

      <form
        className="min-w-0 rounded-lg border border-slate-200 bg-white p-4 sm:p-5"
        onSubmit={(event) => void saveWorkflow(event)}
      >
        <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            <h2 className="text-base font-semibold">
              {selectedWorkflow ? "Edit workflow" : "Create workflow"}
            </h2>
            <p className="text-xs text-slate-500">
              Visual graph plus OpenClaw orchestrator/delegate mapping.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button onClick={resetForm} type="button" variant="outline">
              New
            </Button>
            <Button disabled={!selectedId || loading} onClick={deleteWorkflow} type="button" variant="outline">
              <Trash2 className="mr-2 size-4" />
              Delete
            </Button>
            <Button disabled={!selectedId || loading} onClick={() => void startRun()} type="button" variant="outline">
              <Play className="mr-2 size-4" />
              Run
            </Button>
            <Button disabled={loading} type="submit">
              {loading ? (
                <Loader2 className="mr-2 size-4 animate-spin" />
              ) : (
                <Save className="mr-2 size-4" />
              )}
              Save
            </Button>
          </div>
        </div>

        {error ? (
          <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        <div className="grid min-w-0 items-start gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
          <div className="grid min-w-0 content-start gap-4">
            <Field label="Name">
              <Input
                onChange={(event) => setForm({ ...form, name: event.target.value })}
                required
                value={form.name}
              />
            </Field>
            <Field label="Description">
              <Textarea
                onChange={(event) =>
                  setForm({ ...form, description: event.target.value })
                }
                value={form.description}
              />
            </Field>
            <GraphBuilder
              graph={previewGraph}
              onAddEdge={addGraphEdge}
              onAddNode={addGraphNode}
              onRemoveEdge={removeGraphEdge}
              onRemoveNode={removeGraphNode}
              onSelectNode={setSelectedGraphNodeId}
              onUpdateEdge={updateGraphEdge}
              onUpdateNode={updateGraphNode}
              selectedNodeId={selectedGraphNodeId}
            />
            <Field label="Graph JSON">
              <Textarea
                className="min-h-[320px] font-mono text-xs"
                onChange={(event) => setGraphText(event.target.value)}
                spellCheck={false}
                value={graphText}
              />
            </Field>
          </div>

          <div className="grid min-w-0 content-start gap-4">
            <WorkflowPreview
              graph={previewGraph}
              onNodeMove={(nodeId, position) =>
                updateGraphNode(nodeId, { position })
              }
              onNodeSelect={setSelectedGraphNodeId}
              run={selectedRun}
              selectedNodeId={selectedGraphNodeId}
            />
            <WorkflowRuns
              onRefresh={() => void loadRuns()}
              onSelect={setSelectedRunId}
              runs={runs}
              selectedRunId={selectedRun?.id ?? null}
            />
            <WorkflowRunDetail run={selectedRun} />
          </div>
        </div>
      </form>
    </div>
  );
}

function WorkflowRuns({
  onRefresh,
  onSelect,
  runs,
  selectedRunId,
}: {
  onRefresh: () => void;
  onSelect: (runId: string) => void;
  runs: WorkflowRun[];
  selectedRunId: string | null;
}) {
  return (
    <div className="min-w-0 rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold">Recent Runs</h3>
          <p className="text-xs text-slate-500">{runs.length} run records</p>
        </div>
        <Button onClick={onRefresh} size="sm" type="button" variant="outline">
          <RefreshCcw className="size-4" />
        </Button>
      </div>
      <div className="grid max-h-72 min-w-0 gap-3 overflow-auto">
        {runs.length === 0 ? (
          <p className="rounded-md border border-dashed border-slate-200 p-3 text-sm text-slate-500">
            No runs yet.
          </p>
        ) : null}
        {runs.map((run) => (
          <button
            className={`min-w-0 rounded-md border p-3 text-left ${
              selectedRunId === run.id ? "border-slate-400 bg-slate-50" : "border-slate-200"
            }`}
            key={run.id}
            onClick={() => onSelect(run.id)}
            type="button"
          >
            <div className="mb-2 flex min-w-0 items-center justify-between gap-3">
              <span className="font-mono text-xs text-slate-500">
                {run.id.slice(0, 8)}
              </span>
              <RunStatus status={run.status} />
            </div>
            <div className="mb-2 flex items-center gap-1 text-xs text-slate-500">
              <Clock3 className="size-3" />
              {formatDateTime(run.created_at)}
            </div>
            <div className="grid min-w-0 gap-1">
              {run.nodes.map((node) => (
                <div
                  className="flex items-center justify-between gap-3 text-xs"
                  key={node.id}
                >
                  <span className="truncate text-slate-700">{node.label}</span>
                  <RunStatus status={node.status} />
                </div>
              ))}
            </div>
            {run.error ? (
              <p className="mt-2 line-clamp-2 text-xs text-red-700">{run.error}</p>
            ) : null}
          </button>
        ))}
      </div>
    </div>
  );
}

function WorkflowRunDetail({ run }: { run: WorkflowRun | null }) {
  if (!run) {
    return null;
  }

  return (
    <div className="min-w-0 rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold">Run Detail</h3>
          <p className="break-all font-mono text-xs text-slate-500">{run.id}</p>
        </div>
        <RunStatus status={run.status} />
      </div>

      <div className="mb-4 grid gap-2 text-xs text-slate-600 sm:grid-cols-2">
        <Metric label="Started" value={formatNullableDate(run.started_at)} />
        <Metric label="Completed" value={formatNullableDate(run.completed_at)} />
        <Metric label="Updated" value={formatNullableDate(run.updated_at)} />
        <Metric label="Trigger" value={compactJson(run.trigger)} />
      </div>

      {run.error ? (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {run.error}
        </div>
      ) : null}

      <div className="grid gap-3">
        {run.nodes.map((node) => (
          <div className="min-w-0 rounded-md border border-slate-200 p-3" key={node.id}>
            <div className="mb-2 flex min-w-0 items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-medium">{node.label}</p>
                <p className="truncate font-mono text-xs text-slate-500">{node.node_id}</p>
              </div>
              <RunStatus status={node.status} />
            </div>
            <div className="mb-2 grid gap-2 text-xs text-slate-600 sm:grid-cols-3">
              <Metric label="Type" value={node.node_type} />
              <Metric label="Runtime" value={String(node.output.runtime ?? "-")} />
              <Metric label="Model" value={String(node.output.model ?? "-")} />
            </div>
            <pre className="max-h-52 max-w-full overflow-auto whitespace-pre-wrap break-words rounded-md bg-slate-950 p-3 text-xs text-slate-100">
              {JSON.stringify(node.output, null, 2)}
            </pre>
            {node.error ? (
              <p className="mt-2 text-xs text-red-700">{node.error}</p>
            ) : null}
          </div>
        ))}
      </div>

      <div className="mt-4">
        <h4 className="mb-2 text-sm font-semibold">Logs</h4>
        <div className="grid max-h-48 min-w-0 gap-2 overflow-auto">
          {run.logs.length === 0 ? (
            <p className="rounded-md border border-dashed border-slate-200 p-3 text-sm text-slate-500">
              No logs recorded.
            </p>
          ) : null}
          {run.logs.map((log) => (
            <div className="min-w-0 rounded-md border border-slate-200 p-2 text-xs" key={log.id}>
              <div className="flex min-w-0 items-center justify-between gap-3">
                <span className="truncate font-medium text-slate-700">{log.message}</span>
                <span className="shrink-0 text-slate-500">{formatDateTime(log.created_at)}</span>
              </div>
              <p className="mt-1 text-slate-500">{log.level}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-md bg-slate-50 p-2">
      <p className="text-[11px] font-medium uppercase text-slate-400">{label}</p>
      <p className="truncate text-xs text-slate-700">{value}</p>
    </div>
  );
}

function RunStatus({ status }: { status: string }) {
  const tone =
    status === "succeeded"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : status === "failed"
        ? "border-red-200 bg-red-50 text-red-700"
        : status === "running"
          ? "border-blue-200 bg-blue-50 text-blue-700"
          : "border-slate-200 bg-slate-50 text-slate-600";

  return (
    <span className={`rounded border px-2 py-0.5 text-xs font-medium ${tone}`}>
      {status}
    </span>
  );
}

function GraphBuilder({
  graph,
  onAddEdge,
  onAddNode,
  onRemoveEdge,
  onRemoveNode,
  onSelectNode,
  onUpdateEdge,
  onUpdateNode,
  selectedNodeId,
}: {
  graph: WorkflowGraph;
  onAddEdge: () => void;
  onAddNode: (type: "agent" | "condition") => void;
  onRemoveEdge: (edgeId: string) => void;
  onRemoveNode: (nodeId: string) => void;
  onSelectNode: (nodeId: string | null) => void;
  onUpdateEdge: (edgeId: string, patch: Partial<WorkflowEdge>) => void;
  onUpdateNode: (nodeId: string, patch: Partial<WorkflowNode>) => void;
  selectedNodeId: string | null;
}) {
  const selectedNode =
    graph.nodes.find((node) => node.id === selectedNodeId) ?? graph.nodes[0] ?? null;

  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold">Graph Builder</p>
          <p className="text-xs text-slate-500">
            {graph.nodes.length} nodes · {graph.edges.length} edges
          </p>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => onAddNode("agent")} size="sm" type="button" variant="outline">
            <Plus className="mr-1 size-3" />
            Agent
          </Button>
          <Button onClick={() => onAddNode("condition")} size="sm" type="button" variant="outline">
            <Plus className="mr-1 size-3" />
            Condition
          </Button>
        </div>
      </div>

      <div className="grid gap-3">
        <Field label="Selected node">
          <select
            className="flex h-10 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-slate-300"
            onChange={(event) => onSelectNode(event.target.value || null)}
            value={selectedNode?.id ?? ""}
          >
            {graph.nodes.length === 0 ? <option value="">No nodes</option> : null}
            {graph.nodes.map((node) => (
              <option key={node.id} value={node.id}>
                {node.label ?? node.id}
              </option>
            ))}
          </select>
        </Field>

        {selectedNode ? (
          <div className="grid gap-3 rounded-md border border-slate-200 bg-white p-3">
            <Field label="Label">
              <Input
                onChange={(event) =>
                  onUpdateNode(selectedNode.id, { label: event.target.value })
                }
                value={selectedNode.label ?? ""}
              />
            </Field>
            <Field label={selectedNode.type === "condition" ? "Condition" : "Role"}>
              <Input
                onChange={(event) =>
                  onUpdateNode(
                    selectedNode.id,
                    selectedNode.type === "condition"
                      ? { condition: event.target.value }
                      : { role: event.target.value },
                  )
                }
                value={
                  selectedNode.type === "condition"
                    ? selectedNode.condition ?? ""
                    : selectedNode.role ?? ""
                }
              />
            </Field>
            <div className="grid grid-cols-2 gap-2">
              <Field label="X">
                <Input
                  onChange={(event) =>
                    onUpdateNode(selectedNode.id, {
                      position: {
                        x: Number(event.target.value),
                        y: selectedNode.position?.y ?? 120,
                      },
                    })
                  }
                  type="number"
                  value={selectedNode.position?.x ?? 0}
                />
              </Field>
              <Field label="Y">
                <Input
                  onChange={(event) =>
                    onUpdateNode(selectedNode.id, {
                      position: {
                        x: selectedNode.position?.x ?? 80,
                        y: Number(event.target.value),
                      },
                    })
                  }
                  type="number"
                  value={selectedNode.position?.y ?? 0}
                />
              </Field>
            </div>
            <Button
              disabled={graph.nodes.length <= 1}
              onClick={() => onRemoveNode(selectedNode.id)}
              size="sm"
              type="button"
              variant="outline"
            >
              <Trash2 className="mr-2 size-4" />
              Remove node
            </Button>
          </div>
        ) : null}

        <div className="rounded-md border border-slate-200 bg-white p-3">
          <div className="mb-2 flex items-center justify-between gap-3">
            <p className="text-xs font-medium text-slate-500">Edges</p>
            <Button
              disabled={graph.nodes.length < 2}
              onClick={onAddEdge}
              size="sm"
              type="button"
              variant="outline"
            >
              <Plus className="mr-1 size-3" />
              Edge
            </Button>
          </div>
          <div className="grid gap-2">
            {graph.edges.length === 0 ? (
              <p className="rounded-md border border-dashed border-slate-200 p-2 text-xs text-slate-500">
                No edges yet.
              </p>
            ) : null}
            {graph.edges.map((edge) => (
              <div className="grid gap-2 rounded-md border border-slate-200 p-2" key={edge.id}>
                <Input
                  aria-label="Edge label"
                  onChange={(event) =>
                    onUpdateEdge(edge.id, { label: event.target.value })
                  }
                  value={edge.label ?? ""}
                />
                <div className="grid grid-cols-[1fr_1fr_auto] gap-2">
                  <select
                    aria-label="Edge source"
                    className="h-9 rounded-md border border-slate-200 bg-white px-2 text-xs outline-none focus-visible:ring-2 focus-visible:ring-slate-300"
                    onChange={(event) =>
                      onUpdateEdge(edge.id, { source: event.target.value })
                    }
                    value={edge.source}
                  >
                    {graph.nodes.map((node) => (
                      <option key={node.id} value={node.id}>
                        {node.label ?? node.id}
                      </option>
                    ))}
                  </select>
                  <select
                    aria-label="Edge target"
                    className="h-9 rounded-md border border-slate-200 bg-white px-2 text-xs outline-none focus-visible:ring-2 focus-visible:ring-slate-300"
                    onChange={(event) =>
                      onUpdateEdge(edge.id, { target: event.target.value })
                    }
                    value={edge.target}
                  >
                    {graph.nodes.map((node) => (
                      <option key={node.id} value={node.id}>
                        {node.label ?? node.id}
                      </option>
                    ))}
                  </select>
                  <Button
                    onClick={() => onRemoveEdge(edge.id)}
                    size="sm"
                    type="button"
                    variant="outline"
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function WorkflowPreview({
  graph,
  onNodeMove,
  onNodeSelect,
  run,
  selectedNodeId,
}: {
  graph: WorkflowGraph;
  onNodeMove: (nodeId: string, position: { x: number; y: number }) => void;
  onNodeSelect: (nodeId: string) => void;
  run: WorkflowRun | null;
  selectedNodeId: string | null;
}) {
  const runNodeStatus = useMemo(() => {
    return new Map(run?.nodes.map((node) => [node.node_id, node.status]) ?? []);
  }, [run]);
  const terminalStatus = useMemo(() => {
    return (terminalId: string) => {
      const explicitStatus = runNodeStatus.get(terminalId);
      if (explicitStatus || !run) {
        return explicitStatus;
      }

      const upstreamStatuses = graph.edges
        .filter((edge) => edge.target === terminalId)
        .map((edge) => runNodeStatus.get(edge.source))
        .filter(Boolean);

      if (upstreamStatuses.includes("failed")) {
        return "failed";
      }
      if (upstreamStatuses.includes("running")) {
        return "running";
      }
      if (
        run.status === "succeeded" &&
        upstreamStatuses.length > 0 &&
        upstreamStatuses.every((status) => status === "succeeded")
      ) {
        return "succeeded";
      }
      return undefined;
    };
  }, [graph.edges, run, runNodeStatus]);
  const flowNodes = useMemo<Node<FlowNodeData>[]>(() => {
    const declaredNodes = graph.nodes.map((node, index) => {
      const position = node.position ?? { x: index * 280, y: 80 };
      return {
        data: {
          condition: node.condition,
          label: node.label ?? node.id,
          nodeType: node.type,
          role: node.role,
          selected: node.id === selectedNodeId,
          status: runNodeStatus.get(node.id),
        },
        draggable: true,
        id: node.id,
        position,
        type: "workflow",
      };
    });
    const declaredIds = new Set(graph.nodes.map((node) => node.id));
    const missingEndpointIds = Array.from(
      new Set(
        graph.edges
          .flatMap((edge) => [edge.source, edge.target])
          .filter((id) => !declaredIds.has(id)),
      ),
    );
    const maxX = declaredNodes.reduce(
      (value, node) => Math.max(value, node.position.x),
      0,
    );
    const generatedNodes = missingEndpointIds.map((id, index) => ({
      data: {
        generated: true,
        label: id,
        nodeType: "terminal",
        selected: id === selectedNodeId,
        status: terminalStatus(id),
      },
      draggable: false,
      id,
      position: { x: maxX + 280, y: 80 + index * 120 },
      type: "workflow",
    }));
    return [...declaredNodes, ...generatedNodes];
  }, [graph.edges, graph.nodes, runNodeStatus, selectedNodeId, terminalStatus]);
  const flowEdges = useMemo<Edge[]>(() => {
    return graph.edges.map((edge) => ({
      animated: Boolean(edge.condition),
      data: { condition: edge.condition },
      id: edge.id,
      label: edge.label,
      markerEnd: { type: MarkerType.ArrowClosed },
      source: edge.source,
      style: {
        stroke: edge.condition ? "#d97706" : "#64748b",
        strokeDasharray: edge.condition ? "6 4" : undefined,
        strokeWidth: 3,
      },
      target: edge.target,
      type: "smoothstep",
    }));
  }, [graph.edges]);
  const flowKey = useMemo(
    () => flowNodes.map((node) => node.id).join("|"),
    [flowNodes],
  );

  return (
    <div className="min-w-0 rounded-lg border border-slate-200 bg-slate-50 p-4">
      <div className="mb-3">
        <h3 className="text-sm font-semibold">Builder Preview</h3>
        <p className="text-xs text-slate-500">
          {graph.nodes.length} nodes · {graph.edges.length} edges ·{" "}
          {String(graph.openclaw.strategy ?? "no strategy")}
        </p>
      </div>
      <div className="h-[360px] max-w-full overflow-hidden rounded-md border border-slate-200 bg-white">
        <ReactFlow
          colorMode="light"
          edges={flowEdges}
          fitView
          fitViewOptions={{ padding: 0.18 }}
          key={flowKey}
          maxZoom={1.4}
          minZoom={0.25}
          nodes={flowNodes}
          nodesConnectable={false}
          nodesDraggable
          nodeTypes={nodeTypes}
          onNodeClick={(_, node) => onNodeSelect(node.id)}
          onNodeDragStop={(_, node) => {
            if (graph.nodes.some((graphNode) => graphNode.id === node.id)) {
              onNodeMove(node.id, {
                x: Math.round(node.position.x),
                y: Math.round(node.position.y),
              });
            }
          }}
          panOnDrag
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#e2e8f0" gap={18} />
          <Controls showInteractive={false} />
          <MiniMap
            nodeColor={(node) => statusColor(String(node.data?.status ?? ""))}
            pannable
            style={{ height: 72, width: 112 }}
            zoomable
          />
        </ReactFlow>
      </div>
    </div>
  );
}

function WorkflowFlowNode({ data }: NodeProps<Node<FlowNodeData>>) {
  const status = data.status ?? "idle";
  const isCondition = data.nodeType === "condition";
  const isGenerated = data.generated;
  return (
    <div
      className={`w-44 rounded-md border bg-white px-3 py-2 shadow-sm ${
        data.selected
          ? "border-blue-400 ring-2 ring-blue-100"
          : isGenerated
          ? "border-dashed border-slate-300 bg-slate-50"
          : isCondition
            ? "border-amber-300"
            : "border-slate-200"
      }`}
    >
      <Handle className="!size-2 !bg-slate-400" position={Position.Left} type="target" />
      <div className="flex min-w-0 items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-slate-950">{data.label}</p>
          <p className="mt-1 line-clamp-2 text-xs text-slate-500">
            {data.role ?? data.condition ?? data.nodeType}
          </p>
        </div>
        <span
          className="mt-0.5 size-2.5 shrink-0 rounded-full"
          style={{ backgroundColor: statusColor(status) }}
          title={status}
        />
      </div>
      <div className="mt-2 flex items-center justify-between gap-2 text-[11px] text-slate-500">
        <span className="truncate">{data.nodeType}</span>
        <span className="truncate">{status}</span>
      </div>
      <Handle className="!size-2 !bg-slate-400" position={Position.Right} type="source" />
    </div>
  );
}

function Field({
  children,
  label,
}: {
  children: React.ReactNode;
  label: string;
}) {
  return (
    <div className="grid gap-2">
      <Label>{label}</Label>
      {children}
    </div>
  );
}

function WorkflowGraphSchema(value: WorkflowGraph): WorkflowGraph {
  return {
    edges: Array.isArray(value.edges) ? value.edges : [],
    nodes: Array.isArray(value.nodes) ? value.nodes : [],
    openclaw: value.openclaw && typeof value.openclaw === "object" ? value.openclaw : {},
  };
}

function formatNullableDate(value: string | null) {
  return value ? formatDateTime(value) : "-";
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(new Date(value));
}

function compactJson(value: Record<string, unknown>) {
  const text = JSON.stringify(value);
  return text.length > 80 ? `${text.slice(0, 77)}...` : text;
}

function uniqueGraphId(graph: WorkflowGraph, prefix: string) {
  const existing = new Set([
    ...graph.nodes.map((node) => node.id),
    ...graph.edges.map((edge) => edge.id),
  ]);
  let index = existing.size + 1;
  let id = `${prefix}-${index}`;
  while (existing.has(id)) {
    index += 1;
    id = `${prefix}-${index}`;
  }
  return id;
}

function statusColor(status: string) {
  switch (status) {
    case "succeeded":
      return "#059669";
    case "failed":
      return "#dc2626";
    case "running":
      return "#2563eb";
    case "queued":
      return "#64748b";
    default:
      return "#94a3b8";
  }
}
