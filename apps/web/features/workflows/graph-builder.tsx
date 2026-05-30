import { Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";

import { Field } from "./field";
import type { WorkflowAgent, WorkflowEdge, WorkflowGraph, WorkflowNode } from "./types";

export function GraphBuilder({
  graph,
  agents,
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
  agents: WorkflowAgent[];
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
            {selectedNode.type === "condition" ? (
              <Field label="Condition">
                <Input
                  onChange={(event) =>
                    onUpdateNode(selectedNode.id, { condition: event.target.value })
                  }
                  value={selectedNode.condition ?? ""}
                />
              </Field>
            ) : (
              <div className="grid gap-3">
                <Field label="Agent">
                  <select
                    className="flex h-10 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-slate-300"
                    onChange={(event) =>
                      onUpdateNode(selectedNode.id, {
                        agent_id: event.target.value || null,
                      })
                    }
                    value={selectedNode.agent_id ?? ""}
                  >
                    <option value="">Unassigned</option>
                    {agents.map((agent) => (
                      <option key={agent.id} value={agent.id}>
                        {agent.name}
                      </option>
                    ))}
                  </select>
                </Field>
                {selectedNode.agent_id ? (
                  <p className="text-xs text-slate-500">
                    {agents.find((agent) => agent.id === selectedNode.agent_id)?.role ??
                      "Selected agent"}
                  </p>
                ) : null}
                <Field label="Role">
                  <Input
                    onChange={(event) =>
                      onUpdateNode(selectedNode.id, { role: event.target.value })
                    }
                    value={selectedNode.role ?? ""}
                  />
                </Field>
                <label className="flex items-center gap-2 text-sm text-slate-700">
                  <Checkbox
                    checked={Boolean(selectedNode.reply)}
                    onCheckedChange={(checked) =>
                      onUpdateNode(selectedNode.id, { reply: checked === true })
                    }
                  />
                  Final reply
                </label>
              </div>
            )}
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
