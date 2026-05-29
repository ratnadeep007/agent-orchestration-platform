import { Suspense } from "react";
import { Activity, Bot, GitBranch, Server } from "lucide-react";

import { HomeTabs } from "./home-tabs";

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const items = [
  { label: "Agents", value: "scaffold", icon: Bot },
  { label: "Workflows", value: "scaffold", icon: GitBranch },
  { label: "Monitoring", value: "scaffold", icon: Activity },
  { label: "API", value: apiUrl, icon: Server },
];

export default function Home() {
  return (
    <main className="min-h-screen bg-slate-50 px-4 py-6 text-slate-950 sm:px-6 lg:px-8">
      <section className="mx-auto flex max-w-7xl flex-col gap-6">
        <div className="flex flex-col gap-2 border-b border-slate-200 pb-6">
          <p className="text-sm font-medium text-slate-500">
            Agent Orchestration
          </p>
          <h1 className="text-3xl font-semibold tracking-normal">
            Agent Orchestration Platform
          </h1>
          <p className="max-w-2xl text-sm leading-6 text-slate-600">
            Bootable monorepo scaffold for the challenge. Product features are
            intentionally pending.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {items.map((item) => {
            const Icon = item.icon;

            return (
              <div
                className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
                key={item.label}
              >
                <div className="flex items-center gap-3">
                  <div className="flex size-9 items-center justify-center rounded-md border border-slate-200 bg-slate-50">
                    <Icon className="size-4" />
                  </div>
                  <div>
                    <p className="text-sm font-medium">{item.label}</p>
                    <p className="mt-1 break-all text-xs text-slate-500">
                      {item.value}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <Suspense fallback={null}>
          <HomeTabs />
        </Suspense>
      </section>
    </main>
  );
}
