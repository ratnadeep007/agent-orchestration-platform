"use client";

import { useEffect, useState } from "react";
import { MessageSquare, RefreshCcw } from "lucide-react";

import { Button } from "@/components/ui/button";

type Message = {
  id: string;
  run_id: string | null;
  agent_id: string | null;
  channel: string;
  direction: "inbound" | "outbound" | "agent";
  body: string;
  delivery_state: string;
  external_id: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function MessagesClient() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void loadMessages();
  }, []);

  async function loadMessages() {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiUrl}/messages`, { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`Message load failed: ${response.status}`);
      }
      setMessages(await response.json());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Message load failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white">
      <div className="flex items-center justify-between border-b border-slate-200 p-4">
        <div>
          <h2 className="text-sm font-semibold">Message History</h2>
          <p className="text-xs text-slate-500">
            Runtime, Telegram, and inter-agent messages mirrored into Postgres.
          </p>
        </div>
        <Button
          disabled={loading}
          onClick={() => void loadMessages()}
          type="button"
          variant="outline"
        >
          <RefreshCcw className="mr-2 size-4" />
          Refresh
        </Button>
      </div>

      {error ? (
        <div className="m-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      <div className="grid gap-3 p-4">
        {messages.length === 0 ? (
          <div className="rounded-md border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
            No mirrored messages yet.
          </div>
        ) : null}
        {messages.map((message) => (
          <article
            className="rounded-md border border-slate-200 bg-slate-50 p-4"
            key={message.id}
          >
            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <MessageSquare className="size-4" />
              <span>{message.channel}</span>
              <span>·</span>
              <span>{message.direction}</span>
              <span>·</span>
              <span>{message.delivery_state}</span>
              <span>·</span>
              <time dateTime={message.created_at}>
                {new Date(message.created_at).toLocaleString()}
              </time>
            </div>
            <p className="mt-3 whitespace-pre-wrap text-sm text-slate-900">
              {message.body}
            </p>
            <dl className="mt-3 grid gap-1 text-xs text-slate-500 sm:grid-cols-2">
              <div>
                <dt className="font-medium">External ID</dt>
                <dd className="break-all">{message.external_id ?? "none"}</dd>
              </div>
              <div>
                <dt className="font-medium">Source</dt>
                <dd>{String(message.metadata.source ?? "app")}</dd>
              </div>
            </dl>
          </article>
        ))}
      </div>
    </section>
  );
}
