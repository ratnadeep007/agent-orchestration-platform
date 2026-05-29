"use client";

import { Activity, Bot, GitBranch } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { AgentsClient } from "./agents-client";
import { MessagesClient } from "./messages-client";
import { WorkflowsClient } from "./workflows-client";

const tabValues = ["agents", "workflows", "messages"] as const;
type HomeTab = (typeof tabValues)[number];

function isHomeTab(value: string | null): value is HomeTab {
  return tabValues.includes(value as HomeTab);
}

export function HomeTabs() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedTab = searchParams.get("tab");
  const activeTab: HomeTab = isHomeTab(requestedTab) ? requestedTab : "agents";

  function handleTabChange(value: string) {
    if (!isHomeTab(value)) {
      return;
    }

    const params = new URLSearchParams(searchParams);
    params.set("tab", value);
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  }

  return (
    <Tabs
      className="w-full min-w-0"
      onValueChange={handleTabChange}
      value={activeTab}
    >
      <TabsList>
        <TabsTrigger value="agents">
          <Bot className="mr-2 size-4" />
          Agents
        </TabsTrigger>
        <TabsTrigger value="workflows">
          <GitBranch className="mr-2 size-4" />
          Workflows
        </TabsTrigger>
        <TabsTrigger value="messages">
          <Activity className="mr-2 size-4" />
          Messages
        </TabsTrigger>
      </TabsList>
      <TabsContent value="agents">
        <AgentsClient />
      </TabsContent>
      <TabsContent value="workflows">
        <WorkflowsClient />
      </TabsContent>
      <TabsContent value="messages">
        <MessagesClient />
      </TabsContent>
    </Tabs>
  );
}
