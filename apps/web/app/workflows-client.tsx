"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { GitBranch, Loader2, Play, Plus, RefreshCcw, Save, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Field } from "@/features/workflows/field";
import { GraphBuilder } from "@/features/workflows/graph-builder";
import { WorkflowRuns, WorkflowRunDetail } from "@/features/workflows/run-panels";
import { WorkflowPreview } from "@/features/workflows/workflow-preview";
import type {
  WorkflowAgent,
  Workflow,
  WorkflowEdge,
  WorkflowGraph,
  WorkflowNode,
  WorkflowPayload,
  WorkflowRun,
  WorkflowTemplate,
} from "@/features/workflows/types";
import { uniqueGraphId, workflowGraphSchema } from "@/features/workflows/utils";

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const demoAgentIds = {
  delegate: "22222222-2222-2222-2222-222222222222",
  orchestrator: "11111111-1111-1111-1111-111111111111",
  reviewer: "66666666-6666-6666-6666-666666666666",
};

const emptyGraph: WorkflowGraph = {
  nodes: [
    {
      agent_id: demoAgentIds.orchestrator,
      id: "orchestrator",
      label: "Orchestrator",
      role: "Route work to delegates",
      type: "agent",
      position: { x: 80, y: 120 },
    },
    {
      agent_id: demoAgentIds.delegate,
      id: "delegate",
      label: "Delegate",
      role: "Complete assigned work",
      reply: true,
      type: "agent",
      position: { x: 360, y: 120 },
    },
    {
      agent_id: demoAgentIds.reviewer,
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
  telegram_command: null,
};

export function WorkflowsClient() {
  const [agents, setAgents] = useState<WorkflowAgent[]>([]);
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
  const agentsById = useMemo(
    () => new Map(agents.map((agent) => [agent.id, agent])),
    [agents],
  );

  useEffect(() => {
    void loadAll();
  }, []);

  async function loadAll() {
    setLoading(true);
    setError(null);
    try {
      const [agentResponse, workflowResponse, templateResponse] = await Promise.all([
        fetch(`${apiUrl}/agents`, { cache: "no-store" }),
        fetch(`${apiUrl}/workflows`, { cache: "no-store" }),
        fetch(`${apiUrl}/workflows/templates`, { cache: "no-store" }),
      ]);
      if (!agentResponse.ok || !workflowResponse.ok || !templateResponse.ok) {
        throw new Error("Workflow load failed");
      }
      setAgents(await agentResponse.json());
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
      telegram_command: workflow.telegram_command ?? null,
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
      const current = workflowGraphSchema(JSON.parse(graphText));
      const next = workflowGraphSchema(updater(current));
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
        agent_id: type === "agent" && agents[0] ? agents[0].id : null,
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
      return workflowGraphSchema(JSON.parse(graphText));
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
                <span className="block text-xs text-slate-500">
                  {workflow.telegram_command ? `/${workflow.telegram_command}` : "no telegram command"}
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
            <Field label="Telegram Command">
              <Input
                onChange={(event) =>
                  setForm({
                    ...form,
                    telegram_command: event.target.value.replace(/^\//, "").trim() || null,
                  })
                }
                placeholder="research"
                value={form.telegram_command ?? ""}
              />
            </Field>
              <GraphBuilder
                graph={previewGraph}
                agents={agents}
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
              agents={agentsById}
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
