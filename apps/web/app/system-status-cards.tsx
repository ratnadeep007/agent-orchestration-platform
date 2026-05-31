"use client";

import { Activity, Server } from "lucide-react";
import { useEffect, useState } from "react";

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type StatusState = {
  api: boolean | null;
  worker: boolean | null;
  loading: boolean;
};

export function SystemStatusCards() {
  const [state, setState] = useState<StatusState>({
    api: false,
    worker: false,
    loading: true,
  });

  useEffect(() => {
    let cancelled = false;
    let timer: number | null = null;

    const loadStatus = async () => {
      try {
        const [healthResponse, readyResponse] = await Promise.all([
          fetch(`${apiUrl}/health`, { cache: "no-store" }),
          fetch(`${apiUrl}/ready`, { cache: "no-store" }),
        ]);
        const ready = readyResponse.ok ? await readyResponse.json() : {};
        if (!cancelled) {
          setState({
            api: healthResponse.ok,
            worker: Boolean(ready.worker_reachable),
            loading: false,
          });
        }
      } catch {
        if (!cancelled) {
          setState({ api: false, worker: false, loading: false });
        }
      }
      if (!cancelled) {
        timer = window.setTimeout(loadStatus, 5000);
      }
    };

    void loadStatus();

    return () => {
      cancelled = true;
      if (timer !== null) {
        window.clearTimeout(timer);
      }
    };
  }, []);

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <StatusCard
        active={state.api}
        icon={Server}
        label="API"
        loading={state.loading || state.api === null}
        value={state.loading ? "Checking..." : state.api ? "Active" : "Offline"}
      />
      <StatusCard
        active={state.worker}
        icon={Activity}
        label="Worker"
        loading={state.loading || state.worker === null}
        value={state.loading ? "Checking..." : state.worker ? "Active" : "Offline"}
      />
    </div>
  );
}

function StatusCard({
  active,
  icon: Icon,
  label,
  loading,
  value,
}: {
  active: boolean | null;
  icon: typeof Server;
  loading: boolean;
  label: string;
  value: string;
}) {
  const tone = loading
    ? "border-slate-200 bg-slate-50 text-slate-500"
    : active
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : "border-rose-200 bg-rose-50 text-rose-700";
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-3">
        <div className={`flex size-9 items-center justify-center rounded-md border ${tone}`}>
          <Icon className="size-4" />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-medium">{label}</p>
          <p
            className={`mt-1 flex items-center gap-2 text-xs ${
              loading ? "text-slate-500" : active ? "text-emerald-700" : "text-rose-700"
            }`}
          >
            <span
              className={`size-2 rounded-full ${
                loading ? "bg-slate-400" : active ? "bg-emerald-500" : "bg-rose-500"
              }`}
            />
            {value}
          </p>
        </div>
      </div>
    </div>
  );
}
