import { Clock3, RefreshCcw } from "lucide-react";

import { Button } from "@/components/ui/button";

import type { WorkflowRun } from "./types";

export function WorkflowRuns({
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

export function WorkflowRunDetail({ run }: { run: WorkflowRun | null }) {
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
