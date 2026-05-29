from collections import deque
from typing import Any


def normalize_graph(graph: dict[str, Any]) -> dict[str, Any]:
    return {
        "nodes": graph["nodes"] if isinstance(graph.get("nodes"), list) else [],
        "edges": graph["edges"] if isinstance(graph.get("edges"), list) else [],
        "openclaw": graph["openclaw"] if isinstance(graph.get("openclaw"), dict) else {},
    }


def execution_order(graph: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = [node for node in graph["nodes"] if "id" in node]
    node_ids = {str(node["id"]) for node in nodes}
    by_id = {str(node["id"]): node for node in nodes}
    dependencies: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    dependents: dict[str, set[str]] = {node_id: set() for node_id in node_ids}

    for edge in graph["edges"]:
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        if source in node_ids and target in node_ids and source != target:
            dependencies[target].add(source)
            dependents[source].add(target)

    ready = deque(node_id for node_id in by_id if not dependencies[node_id])
    ordered: list[str] = []
    while ready:
        node_id = ready.popleft()
        if node_id in ordered:
            continue
        ordered.append(node_id)
        for dependent in dependents[node_id]:
            dependencies[dependent].discard(node_id)
            if not dependencies[dependent]:
                ready.append(dependent)

    ordered.extend(node_id for node_id in by_id if node_id not in ordered)
    return [by_id[node_id] for node_id in ordered]


def upstream_outputs(
    node_id: str,
    graph: dict[str, Any],
    outputs: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    upstream = {}
    for edge in graph["edges"]:
        if str(edge.get("target", "")) == node_id:
            source = str(edge.get("source", ""))
            if source in outputs:
                upstream[source] = outputs[source]
    return upstream
