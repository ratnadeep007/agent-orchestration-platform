import { Suspense } from "react";

import { HomeTabs } from "./home-tabs";
import { SystemStatusCards } from "./system-status-cards";

export default function Home() {
  return (
    <main className="min-h-screen bg-slate-50 px-4 py-6 text-slate-950 sm:px-6 lg:px-8">
      <section className="mx-auto flex max-w-7xl flex-col gap-6">
        <div className="flex flex-col gap-2 border-b border-slate-200 pb-6">
          <p className="text-sm font-medium text-slate-500">Agent Orchestration</p>
          <h1 className="text-3xl font-semibold tracking-normal">
            Agent Orchestration Platform
          </h1>
          <p className="max-w-2xl text-sm leading-6 text-slate-600">
            Live console for agents, workflows, messages, and runtime status.
          </p>
        </div>

        <SystemStatusCards />

        <Suspense fallback={null}>
          <HomeTabs />
        </Suspense>
      </section>
    </main>
  );
}
