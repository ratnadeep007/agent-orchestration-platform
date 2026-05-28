"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import type React from "react";
import { Clock3, GitBranch, Loader2, Play, Plus, RefreshCcw, Save, Trash2 } from "lucide-react";

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

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
    void loadRuns(workflow.id);
  }

  function resetForm() {
    setSelectedId(null);
    setForm(emptyWorkflow);
    setGraphText(JSON.stringify(emptyGraph, null, 2));
    setRuns([]);
    setError(null);
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

        <div className="grid min-w-0 gap-4 2xl:grid-cols-[360px_minmax(0,1fr)]">
          <div className="grid min-w-0 gap-4">
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
            <Field label="Graph JSON">
              <Textarea
                className="min-h-[360px] font-mono text-xs"
                onChange={(event) => setGraphText(event.target.value)}
                spellCheck={false}
                value={graphText}
              />
            </Field>
          </div>

          <div className="grid min-w-0 gap-4">
            <WorkflowPreview graph={previewGraph} />
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

function WorkflowPreview({ graph }: { graph: WorkflowGraph }) {
  const layout = getGraphLayout(graph);

  return (
    <div className="min-w-0 rounded-lg border border-slate-200 bg-slate-50 p-4">
      <div className="mb-3">
        <h3 className="text-sm font-semibold">Builder Preview</h3>
        <p className="text-xs text-slate-500">
          {graph.nodes.length} nodes · {graph.edges.length} edges ·{" "}
          {String(graph.openclaw.strategy ?? "no strategy")}
        </p>
      </div>
      <div className="h-[360px] max-w-full overflow-auto rounded-md border border-slate-200 bg-white">
        <div
          className="relative"
          style={{ height: `${layout.height}px`, width: `${layout.width}px` }}
        >
          <svg
            className="absolute inset-0"
            height={layout.height}
            role="presentation"
            width={layout.width}
          >
            {graph.edges.map((edge) => {
              const source = layout.positions.get(edge.source);
              const target = layout.positions.get(edge.target);
              if (!source || !target) {
                return null;
              }
              return (
                <line
                  key={edge.id}
                  stroke="#94a3b8"
                  strokeDasharray={edge.condition ? "5 5" : undefined}
                  strokeWidth="2"
                  x1={source.x + 208}
                  x2={target.x}
                  y1={source.y + 38}
                  y2={target.y + 38}
                />
              );
            })}
          </svg>
          {graph.nodes.map((node) => {
            const position = layout.positions.get(node.id) ?? { x: 48, y: 48 };
            return (
            <div
              className={`absolute w-52 rounded-md border bg-white p-3 shadow-sm ${
                node.type === "condition" ? "border-amber-300" : "border-slate-200"
              }`}
              key={node.id}
              style={{
                left: `${position.x}px`,
                top: `${position.y}px`,
              }}
            >
              <p className="truncate text-sm font-medium">{node.label ?? node.id}</p>
              <p className="mt-1 line-clamp-2 text-xs text-slate-500">
                {node.role ?? node.condition ?? node.type}
              </p>
            </div>
            );
          })}
        </div>
      </div>
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

function getGraphLayout(graph: WorkflowGraph) {
  const nodeWidth = 208;
  const nodeHeight = 92;
  const padding = 48;
  const rawPositions = graph.nodes.map((node, index) => ({
    id: node.id,
    x: node.position?.x ?? index * 280,
    y: node.position?.y ?? 80,
  }));
  const minX = rawPositions.reduce((value, position) => Math.min(value, position.x), 0);
  const minY = rawPositions.reduce((value, position) => Math.min(value, position.y), 0);
  const positions = new Map(
    rawPositions.map((position) => [
      position.id,
      {
        x: position.x - minX + padding,
        y: position.y - minY + padding,
      },
    ]),
  );
  const maxX = Array.from(positions.values()).reduce(
    (value, position) => Math.max(value, position.x),
    padding,
  );
  const maxY = Array.from(positions.values()).reduce(
    (value, position) => Math.max(value, position.y),
    padding,
  );

  return {
    height: Math.max(300, maxY + nodeHeight + padding),
    positions,
    width: Math.max(640, maxX + nodeWidth + padding),
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
