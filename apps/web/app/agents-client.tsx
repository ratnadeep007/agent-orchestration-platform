"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { Bot, Loader2, RefreshCcw, Save, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

import { BUILTIN_TOOL_NAMES, BUILTIN_TOOLS } from "@/features/agents/tool-catalog";

type Agent = AgentPayload & {
  id: string;
  sync_status: string;
  created_at: string;
  updated_at: string;
};

type AgentPayload = {
  name: string;
  role: string;
  system_prompt: string;
  model: string;
  tools: string[];
  channels: string[];
  schedules: Record<string, unknown>[];
  memory: Record<string, unknown>;
  skills: string[];
  interaction_rules: string[];
  guardrails: string[];
};

const emptyAgent: AgentPayload = {
  name: "",
  role: "",
  system_prompt: "",
  model: "gpt-4.1-mini",
  tools: [],
  channels: ["telegram"],
  schedules: [],
  memory: {},
  skills: [],
  interaction_rules: [],
  guardrails: [],
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function AgentsClient() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [form, setForm] = useState<AgentPayload>(emptyAgent);
  const [customToolsText, setCustomToolsText] = useState("");
  const [schedulesText, setSchedulesText] = useState("[]");
  const [memoryText, setMemoryText] = useState("{}");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedAgent = useMemo(
    () => agents.find((agent) => agent.id === selectedId) ?? null,
    [agents, selectedId],
  );

  useEffect(() => {
    void loadAgents();
  }, []);

  function selectAgent(agent: Agent) {
    const customTools = agent.tools.filter((tool) => !BUILTIN_TOOL_NAMES.includes(tool));
    setSelectedId(agent.id);
    setForm({
      name: agent.name,
      role: agent.role,
      system_prompt: agent.system_prompt,
      model: agent.model,
      tools: agent.tools,
      channels: agent.channels,
      schedules: agent.schedules,
      memory: agent.memory,
      skills: agent.skills,
      interaction_rules: agent.interaction_rules,
      guardrails: agent.guardrails,
    });
    setCustomToolsText(customTools.join(", "));
    setSchedulesText(JSON.stringify(agent.schedules, null, 2));
    setMemoryText(JSON.stringify(agent.memory, null, 2));
  }

  function resetForm() {
    setSelectedId(null);
    setForm(emptyAgent);
    setCustomToolsText("");
    setSchedulesText("[]");
    setMemoryText("{}");
    setError(null);
  }

  async function loadAgents() {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${apiUrl}/agents`, { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`Agent load failed: ${response.status}`);
      }
      setAgents(await response.json());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Agent load failed");
    } finally {
      setLoading(false);
    }
  }

  async function saveAgent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const payload = {
        ...form,
        tools: [...selectedBuiltInTools, ...splitList(customToolsText)],
        schedules: JSON.parse(schedulesText),
        memory: JSON.parse(memoryText),
      };
      const response = await fetch(
        selectedId ? `${apiUrl}/agents/${selectedId}` : `${apiUrl}/agents`,
        {
          body: JSON.stringify(payload),
          headers: { "Content-Type": "application/json" },
          method: selectedId ? "PUT" : "POST",
        },
      );
      if (!response.ok) {
        throw new Error(`Agent save failed: ${response.status}`);
      }
      const saved = await response.json();
      await loadAgents();
      selectAgent(saved);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Agent save failed");
    } finally {
      setLoading(false);
    }
  }

  const selectedBuiltInTools = useMemo(
    () => form.tools.filter((tool) => BUILTIN_TOOL_NAMES.includes(tool)),
    [form.tools],
  );

  function setToolSelected(toolName: string, checked: boolean) {
    setForm((current) => {
      const customTools = current.tools.filter((tool) => !BUILTIN_TOOL_NAMES.includes(tool));
      const builtInTools = current.tools.filter((tool) => BUILTIN_TOOL_NAMES.includes(tool));
      const nextBuiltInTools = checked
        ? Array.from(new Set([...builtInTools, toolName]))
        : builtInTools.filter((tool) => tool !== toolName);
      return {
        ...current,
        tools: [...nextBuiltInTools, ...customTools],
      };
    });
  }

  async function deleteAgent() {
    if (!selectedId) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${apiUrl}/agents/${selectedId}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        throw new Error(`Agent delete failed: ${response.status}`);
      }
      resetForm();
      await loadAgents();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Agent delete failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
      <aside className="rounded-lg border border-slate-200 bg-white">
        <div className="flex items-center justify-between border-b border-slate-200 p-4">
          <div>
            <h2 className="text-sm font-semibold">Agents</h2>
            <p className="text-xs text-slate-500">{agents.length} configured</p>
          </div>
          <Button onClick={() => void loadAgents()} size="sm" variant="outline">
            <RefreshCcw className="size-4" />
          </Button>
        </div>

        <div className="max-h-[560px] overflow-auto p-2">
          {agents.map((agent) => (
            <button
              className={`flex w-full items-start gap-3 rounded-md p-3 text-left text-sm hover:bg-slate-50 ${
                selectedId === agent.id ? "bg-slate-100" : ""
              }`}
              key={agent.id}
              onClick={() => selectAgent(agent)}
              type="button"
            >
              <Bot className="mt-0.5 size-4 shrink-0 text-slate-500" />
              <span>
                <span className="block font-medium">{agent.name}</span>
                <span className="block text-xs text-slate-500">
                  {agent.role}
                </span>
              </span>
            </button>
          ))}
        </div>
      </aside>

      <form
        className="rounded-lg border border-slate-200 bg-white p-5"
        onSubmit={(event) => void saveAgent(event)}
      >
        <div className="mb-5 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold">
              {selectedAgent ? "Edit agent" : "Create agent"}
            </h2>
            <p className="text-xs text-slate-500">
              Core fields and runtime config sync into the backend.
            </p>
          </div>
          <div className="flex gap-2">
            <Button onClick={resetForm} type="button" variant="outline">
              New
            </Button>
            <Button disabled={!selectedId || loading} onClick={deleteAgent} type="button" variant="outline">
              <Trash2 className="mr-2 size-4" />
              Delete
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

        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Name">
            <Input
              onChange={(event) => setForm({ ...form, name: event.target.value })}
              required
              value={form.name}
            />
          </Field>
          <Field label="Model">
            <Input
              onChange={(event) => setForm({ ...form, model: event.target.value })}
              required
              value={form.model}
            />
          </Field>
          <Field label="Role">
            <Input
              onChange={(event) => setForm({ ...form, role: event.target.value })}
              required
              value={form.role}
            />
          </Field>
          <Field label="Channels">
            <Input
              onChange={(event) =>
                setForm({ ...form, channels: splitList(event.target.value) })
              }
              value={form.channels.join(", ")}
            />
          </Field>
          <Field className="md:col-span-2" label="Tools">
            <div className="grid gap-3 rounded-md border border-slate-200 bg-slate-50 p-3">
              {BUILTIN_TOOLS.map((tool) => (
                <label className="flex items-start gap-3 text-sm" key={tool.name}>
                  <Checkbox
                    checked={selectedBuiltInTools.includes(tool.name)}
                    onCheckedChange={(checked) =>
                      setToolSelected(tool.name, checked === true)
                    }
                  />
                  <span className="grid gap-0.5">
                    <span className="font-medium">{tool.title}</span>
                    <span className="text-xs text-slate-500">{tool.description}</span>
                  </span>
                </label>
              ))}
            </div>
            <div className="grid gap-2">
              <Label className="text-xs text-slate-500">Custom tools</Label>
              <Input
                onChange={(event) => setCustomToolsText(event.target.value)}
                placeholder="e.g. lookup_invoice, create_ticket"
                value={customToolsText}
              />
            </div>
          </Field>
          <Field label="Skills">
            <Input
              onChange={(event) =>
                setForm({ ...form, skills: splitList(event.target.value) })
              }
              value={form.skills.join(", ")}
            />
          </Field>
          <Field className="md:col-span-2" label="System prompt">
            <Textarea
              onChange={(event) =>
                setForm({ ...form, system_prompt: event.target.value })
              }
              required
              value={form.system_prompt}
            />
          </Field>
          <Field label="Interaction rules">
            <Textarea
              onChange={(event) =>
                setForm({
                  ...form,
                  interaction_rules: splitList(event.target.value),
                })
              }
              value={form.interaction_rules.join("\n")}
            />
          </Field>
          <Field label="Guardrails">
            <Textarea
              onChange={(event) =>
                setForm({ ...form, guardrails: splitList(event.target.value) })
              }
              value={form.guardrails.join("\n")}
            />
          </Field>
          <Field label="Schedules JSON">
            <Textarea
              onChange={(event) => setSchedulesText(event.target.value)}
              spellCheck={false}
              value={schedulesText}
            />
          </Field>
          <Field label="Memory JSON">
            <Textarea
              onChange={(event) => setMemoryText(event.target.value)}
              spellCheck={false}
              value={memoryText}
            />
          </Field>
        </div>
      </form>
    </div>
  );
}

function Field({
  children,
  className,
  label,
}: {
  children: React.ReactNode;
  className?: string;
  label: string;
}) {
  return (
    <div className={`grid gap-2 ${className ?? ""}`}>
      <Label>{label}</Label>
      {children}
    </div>
  );
}

function splitList(value: string) {
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}
