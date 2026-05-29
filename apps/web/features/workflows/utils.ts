import type { WorkflowGraph } from "./types";

export function workflowGraphSchema(value: WorkflowGraph): WorkflowGraph {
  return {
    edges: Array.isArray(value.edges) ? value.edges : [],
    nodes: Array.isArray(value.nodes) ? value.nodes : [],
    openclaw: value.openclaw && typeof value.openclaw === "object" ? value.openclaw : {},
  };
}

export function uniqueGraphId(graph: WorkflowGraph, prefix: string) {
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

export function statusColor(status: string) {
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
