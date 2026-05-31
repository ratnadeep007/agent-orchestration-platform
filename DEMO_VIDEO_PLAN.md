# Demo Video Plan

## Goal
Show the repo end to end in one short recording:
- create or inspect agents
- inspect a workflow template
- send a Telegram message
- watch the workflow run in the UI
- show the final Telegram reply

## Demo Agent Setup
Use the seeded agents already in the repo:
- `Researcher`
- `Writer`
- `Reviewer`
- `Triage`
- `Specialist`
- `Responder`

If you want to show a manual step, create one extra agent in the UI:
- Name: `Demo Synthesizer`
- Role: `Turn upstream findings into a user-facing answer`
- Model: `gpt-4o-mini`
- Channels: `telegram`
- Skill tags: `synthesis`, `response`

## Workflow To Show
Use the `Research Brief` workflow.

Node order:
1. `Researcher`
2. `Writer`
3. `Reviewer`
4. `Ready?`

Mark `Writer` as the `Final reply` node.

## Question To Ask
Use a simple, concrete Telegram prompt:

```text
/research summarize the latest findings on battery recycling
```

Alternative prompts:
- `/support user cannot log in after password reset`
- `plain fallback test for the default workflow`

## What To Narrate
1. The app owns the Telegram webhook and message history.
2. The workflow nodes are bound to reusable agents.
3. The worker executes the workflow and stores run logs and token usage.
4. The final reply node controls what gets sent back to Telegram.

## What To Capture
- Agent list with the demo agents visible
- Workflow editor with `Writer` marked as final reply
- Workflow run detail showing node statuses, logs, and cost rows
- Telegram conversation showing the response

## Recommended Recording Order
1. Open the UI.
2. Show `Agents` and `Workflows`.
3. Send the Telegram prompt.
4. Switch to `Messages` and `Workflows` monitoring while the run completes.
5. Open the run detail and show logs plus cost tracking.
6. End on the Telegram reply.
