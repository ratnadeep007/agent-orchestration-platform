# Agent Orchestration Platform

Monorepo scaffold for an AI agent orchestration challenge.

## Stack

- Frontend: Next.js, TypeScript, shadcn/ui, pnpm
- Backend: FastAPI, Python, uv
- Worker: Python, uv
- Persistence: PostgreSQL
- Queue/cache: Redis
- Agent runtime: OpenClaw Gateway
- External channel: Telegram through OpenClaw

## Local Setup

1. Boot the system:

```bash
docker compose up
```

2. Optional: copy env defaults when you need credentials or local overrides:

```bash
cp .env.example .env
```

3. Fill credentials in `.env` as needed, then restart Compose:

```bash
docker compose up
```

Services:

- Web: http://localhost:3000
- API: http://localhost:8000
- API health: http://localhost:8000/health
- API readiness: http://localhost:8000/ready
- OpenClaw Control UI: http://localhost:18789
- PostgreSQL: localhost:5432
- Redis: localhost:6379

## Database

The API container runs migrations before starting Uvicorn. To run migrations manually:

```bash
docker compose exec api uv run python -m app.migrations
```

Readiness checks include actual Postgres, Redis, and OpenClaw connectivity:

```bash
curl http://localhost:8000/ready
```

## Runtime Decision

OpenClaw is the runtime and channel gateway for this assignment. It owns live agent execution, sessions, memory files, multi-agent routing, and Telegram delivery. The custom app owns the visual UI, app database, workflow/template configuration, monitoring, and the bridge that syncs app-defined agents into OpenClaw-compatible config.

OpenClaw is a better fit than LangGraph for this challenge because Telegram and always-on gateway behavior are central requirements. LangGraph is stronger for graph-native workflow modeling, so the app will keep a visual workflow model and map it into OpenClaw orchestrator/delegate agent configuration.

## OpenClaw Agent Sync

The app database is the source of truth for agent configuration. To sync an app agent into OpenClaw:

```bash
curl -X POST http://localhost:8000/agents/<agent-id>/sync-openclaw
```

The sync writes a generated OpenClaw workspace under `.openclaw/workspace/app-agents/<agent-id>/` and upserts the isolated agent entry in `.openclaw/config/openclaw.json`.

## Runtime Event Mirroring

OpenClaw or Telegram events can be mirrored into the app message history without re-enqueueing delivery:

```bash
curl -X POST http://localhost:8000/messages/runtime-events \
  -H "Content-Type: application/json" \
  -d '{
    "source": "openclaw",
    "event_type": "telegram.message.received",
    "channel": "telegram",
    "direction": "inbound",
    "body": "hello from telegram",
    "external_id": "telegram:message:demo-1",
    "metadata": {"chat_id": "demo"}
  }'
```

Open the Messages tab in the web UI to confirm the mirrored event is visible.

## Telegram Setup

Telegram integration is handled through OpenClaw. The app will mirror Telegram/runtime conversations into PostgreSQL as implementation progresses.

1. Open Telegram and message `@BotFather`.
2. Run `/newbot`.
3. Choose a display name and bot username.
4. Copy the bot token into `.env`:

```bash
TELEGRAM_BOT_TOKEN=your-token-here
```

5. Add the channel to OpenClaw after the gateway is running:

```bash
docker compose run --rm openclaw-cli channels add --channel telegram --token "$TELEGRAM_BOT_TOKEN"
```

6. For a local demo, prefer polling first. Webhooks require a publicly reachable HTTPS URL.
7. After the bot sends/receives a message, record the allowed chat ID in `.env`:

```bash
TELEGRAM_ALLOWED_CHAT_ID=your-chat-id
```

## Monorepo Layout

```text
apps/
  api/      FastAPI service
  web/      Next.js application
  worker/   background worker process
```

Current implementation includes Docker boot wiring, OpenClaw gateway wiring, PostgreSQL migrations, agent CRUD/config API, a shadcn-based agent management UI, and a Redis-backed message delivery queue. Workflow building, OpenClaw config sync, live monitoring, and real Telegram end-to-end behavior are still pending.
The workflow builder can save visual graph JSON, preview nodes/edges, instantiate the built-in Research Brief and Support Triage templates, and preserve OpenClaw orchestrator/delegate mapping metadata. Live monitoring and real Telegram end-to-end behavior are still pending.
