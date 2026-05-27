"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import type React from "react";
import { GitBranch, Loader2, Plus, RefreshCcw, Save, Trash2 } from "lucide-react";

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
  }

  function resetForm() {
    setSelectedId(null);
    setForm(emptyWorkflow);
    setGraphText(JSON.stringify(emptyGraph, null, 2));
    setError(null);
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

  const previewGraph = useMemo(() => {
    try {
      return WorkflowGraphSchema(JSON.parse(graphText));
    } catch {
      return form.graph;
    }
  }, [form.graph, graphText]);

  return (
    <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
      <aside className="rounded-lg border border-slate-200 bg-white">
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
        className="rounded-lg border border-slate-200 bg-white p-5"
        onSubmit={(event) => void saveWorkflow(event)}
      >
        <div className="mb-5 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold">
              {selectedWorkflow ? "Edit workflow" : "Create workflow"}
            </h2>
            <p className="text-xs text-slate-500">
              Visual graph plus OpenClaw orchestrator/delegate mapping.
            </p>
          </div>
          <div className="flex gap-2">
            <Button onClick={resetForm} type="button" variant="outline">
              New
            </Button>
            <Button disabled={!selectedId || loading} onClick={deleteWorkflow} type="button" variant="outline">
              <Trash2 className="mr-2 size-4" />
              Delete
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

        <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr]">
          <div className="grid gap-4">
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

          <WorkflowPreview graph={previewGraph} />
        </div>
      </form>
    </div>
  );
}

function WorkflowPreview({ graph }: { graph: WorkflowGraph }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <div className="mb-3">
        <h3 className="text-sm font-semibold">Builder Preview</h3>
        <p className="text-xs text-slate-500">
          {graph.nodes.length} nodes · {graph.edges.length} edges ·{" "}
          {String(graph.openclaw.strategy ?? "no strategy")}
        </p>
      </div>
      <div className="relative h-[420px] overflow-auto rounded-md border border-slate-200 bg-white">
        <svg className="absolute inset-0 h-full w-full" role="presentation">
          {graph.edges.map((edge) => {
            const source = graph.nodes.find((node) => node.id === edge.source);
            const target = graph.nodes.find((node) => node.id === edge.target);
            if (!source?.position || !target?.position) {
              return null;
            }
            return (
              <line
                key={edge.id}
                stroke="#94a3b8"
                strokeDasharray={edge.condition ? "5 5" : undefined}
                strokeWidth="2"
                x1={source.position.x + 80}
                x2={target.position.x + 20}
                y1={source.position.y + 28}
                y2={target.position.y + 28}
              />
            );
          })}
        </svg>
        {graph.nodes.map((node) => (
          <div
            className={`absolute w-44 rounded-md border bg-white p-3 shadow-sm ${
              node.type === "condition" ? "border-amber-300" : "border-slate-200"
            }`}
            key={node.id}
            style={{
              left: `${node.position?.x ?? 40}px`,
              top: `${node.position?.y ?? 40}px`,
            }}
          >
            <p className="truncate text-sm font-medium">{node.label ?? node.id}</p>
            <p className="mt-1 line-clamp-2 text-xs text-slate-500">
              {node.role ?? node.condition ?? node.type}
            </p>
          </div>
        ))}
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
