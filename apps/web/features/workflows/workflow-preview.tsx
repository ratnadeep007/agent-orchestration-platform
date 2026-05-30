import { useMemo } from "react";
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

import type { FlowNodeData, WorkflowGraph, WorkflowRun } from "./types";
import { statusColor } from "./utils";

const nodeTypes = { workflow: WorkflowFlowNode };

export function WorkflowPreview({
  graph,
  agents,
  onNodeMove,
  onNodeSelect,
  run,
  selectedNodeId,
}: {
  graph: WorkflowGraph;
  agents: Map<string, { id: string; name: string; role: string }>;
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
          agentName: node.agent_id ? agents.get(node.agent_id)?.name : undefined,
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
  }, [agents, graph.edges, graph.nodes, runNodeStatus, selectedNodeId, terminalStatus]);
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
      <div
        className="max-w-full overflow-hidden rounded-md border border-slate-200 bg-white"
        style={{ height: 360 }}
      >
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
          {data.agentName ? (
            <p className="mt-0.5 truncate text-[11px] text-slate-500">
              Agent: {data.agentName}
            </p>
          ) : null}
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
