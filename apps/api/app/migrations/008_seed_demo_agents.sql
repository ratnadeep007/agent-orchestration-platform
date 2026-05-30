INSERT INTO agents (
    id,
    name,
    role,
    system_prompt,
    model,
    tools,
    channels,
    schedules,
    memory,
    skills,
    interaction_rules,
    guardrails,
    sync_status
)
SELECT
    agent_id,
    name,
    role,
    system_prompt,
    'gpt-4o-mini',
    '[]'::jsonb,
    '["telegram"]'::jsonb,
    '[]'::jsonb,
    '{}'::jsonb,
    skill_tags,
    '[]'::jsonb,
    '[]'::jsonb,
    'pending'
FROM (
    VALUES
        (
            '11111111-1111-1111-1111-111111111111'::uuid,
            'Orchestrator',
            'Route work to delegates',
            'You route the incoming request to the right delegate and keep the workflow focused on the user request.',
            '["routing","coordination"]'::jsonb
        ),
        (
            '22222222-2222-2222-2222-222222222222'::uuid,
            'Delegate',
            'Complete assigned work',
            'You execute the assigned work, use upstream context, and report back with a concrete result.',
            '["execution","delivery"]'::jsonb
        ),
        (
            '33333333-3333-3333-3333-333333333333'::uuid,
            'Review',
            'Check readiness',
            'You review upstream work, identify gaps, and decide whether the output is ready to ship.',
            '["review","quality"]'::jsonb
        ),
        (
            '44444444-4444-4444-4444-444444444444'::uuid,
            'Researcher',
            'Collect facts',
            'You gather facts, verify claims, and return a concise evidence-backed research summary.',
            '["research","facts"]'::jsonb
        ),
        (
            '55555555-5555-5555-5555-555555555555'::uuid,
            'Writer',
            'Draft brief',
            'You turn upstream findings into a concise, user-facing draft with the important result first.',
            '["writing","synthesis"]'::jsonb
        ),
        (
            '66666666-6666-6666-6666-666666666666'::uuid,
            'Reviewer',
            'Check quality',
            'You review the draft for clarity, correctness, and readiness, then return a short evaluation.',
            '["review","editing"]'::jsonb
        ),
        (
            '77777777-7777-7777-7777-777777777777'::uuid,
            'Triage',
            'Classify request',
            'You classify the user request, identify the issue category, and choose the appropriate handling path.',
            '["triage","classification"]'::jsonb
        ),
        (
            '88888888-8888-8888-8888-888888888888'::uuid,
            'Specialist',
            'Investigate issue',
            'You investigate the reported issue, gather details, and produce actionable findings.',
            '["investigation","analysis"]'::jsonb
        ),
        (
            '99999999-9999-9999-9999-999999999999'::uuid,
            'Responder',
            'Draft response',
            'You transform the investigation result into a polished response the user can read directly.',
            '["support","response"]'::jsonb
        )
) AS demo_agents(agent_id, name, role, system_prompt, skill_tags)
WHERE NOT EXISTS (
    SELECT 1
    FROM agents
    WHERE agents.id = demo_agents.agent_id
);

UPDATE workflow_templates
SET graph = '{
  "nodes": [
    {"id":"researcher","type":"agent","label":"Researcher","role":"Collect facts","agent_id":"44444444-4444-4444-4444-444444444444","position":{"x":80,"y":120}},
    {"id":"writer","type":"agent","label":"Writer","role":"Draft brief","agent_id":"55555555-5555-5555-5555-555555555555","reply": true,"position":{"x":360,"y":120}},
    {"id":"reviewer","type":"agent","label":"Reviewer","role":"Check quality","agent_id":"66666666-6666-6666-6666-666666666666","position":{"x":640,"y":120}},
    {"id":"approval","type":"condition","label":"Ready?","condition":"quality_score >= 0.8","position":{"x":920,"y":120}}
  ],
  "edges": [
    {"id":"e1","source":"researcher","target":"writer","label":"facts"},
    {"id":"e2","source":"writer","target":"reviewer","label":"draft"},
    {"id":"e3","source":"reviewer","target":"approval","label":"score"},
    {"id":"e4","source":"approval","target":"writer","label":"feedback loop","condition":"not ready"},
    {"id":"e5","source":"approval","target":"done","label":"ready","condition":"ready"}
  ],
  "openclaw": {"strategy":"orchestrator-delegates","orchestrator":"reviewer","delegates":["researcher","writer"]}
}'::jsonb
WHERE name = 'Research Brief';

UPDATE workflow_templates
SET graph = '{
  "nodes": [
    {"id":"triage","type":"agent","label":"Triage","role":"Classify request","agent_id":"77777777-7777-7777-7777-777777777777","position":{"x":80,"y":160}},
    {"id":"specialist","type":"agent","label":"Specialist","role":"Investigate issue","agent_id":"88888888-8888-8888-8888-888888888888","position":{"x":360,"y":160}},
    {"id":"responder","type":"agent","label":"Responder","role":"Draft response","agent_id":"99999999-9999-9999-9999-999999999999","reply": true,"position":{"x":640,"y":160}},
    {"id":"escalate","type":"condition","label":"Escalate?","condition":"severity == high OR confidence < 0.7","position":{"x":920,"y":160}}
  ],
  "edges": [
    {"id":"e1","source":"triage","target":"specialist","label":"classification"},
    {"id":"e2","source":"specialist","target":"responder","label":"findings"},
    {"id":"e3","source":"responder","target":"escalate","label":"draft"},
    {"id":"e4","source":"escalate","target":"specialist","label":"needs more info","condition":"escalate"},
    {"id":"e5","source":"escalate","target":"done","label":"send","condition":"no escalation"}
  ],
  "openclaw": {"strategy":"orchestrator-delegates","orchestrator":"triage","delegates":["specialist","responder"]}
}'::jsonb
WHERE name = 'Support Triage';

UPDATE workflows
SET graph = CASE name
    WHEN 'Research Brief' THEN '{
      "nodes": [
        {"id":"researcher","type":"agent","label":"Researcher","role":"Collect facts","agent_id":"44444444-4444-4444-4444-444444444444","position":{"x":80,"y":120}},
        {"id":"writer","type":"agent","label":"Writer","role":"Draft brief","agent_id":"55555555-5555-5555-5555-555555555555","reply": true,"position":{"x":360,"y":120}},
        {"id":"reviewer","type":"agent","label":"Reviewer","role":"Check quality","agent_id":"66666666-6666-6666-6666-666666666666","position":{"x":640,"y":120}},
        {"id":"approval","type":"condition","label":"Ready?","condition":"quality_score >= 0.8","position":{"x":920,"y":120}}
      ],
      "edges": [
        {"id":"e1","source":"researcher","target":"writer","label":"facts"},
        {"id":"e2","source":"writer","target":"reviewer","label":"draft"},
        {"id":"e3","source":"reviewer","target":"approval","label":"score"},
        {"id":"e4","source":"approval","target":"writer","label":"feedback loop","condition":"not ready"},
        {"id":"e5","source":"approval","target":"done","label":"ready","condition":"ready"}
      ],
      "openclaw": {"strategy":"orchestrator-delegates","orchestrator":"reviewer","delegates":["researcher","writer"]}
    }'::jsonb
    WHEN 'Support Triage' THEN '{
      "nodes": [
        {"id":"triage","type":"agent","label":"Triage","role":"Classify request","agent_id":"77777777-7777-7777-7777-777777777777","position":{"x":80,"y":160}},
        {"id":"specialist","type":"agent","label":"Specialist","role":"Investigate issue","agent_id":"88888888-8888-8888-8888-888888888888","position":{"x":360,"y":160}},
        {"id":"responder","type":"agent","label":"Responder","role":"Draft response","agent_id":"99999999-9999-9999-9999-999999999999","reply": true,"position":{"x":640,"y":160}},
        {"id":"escalate","type":"condition","label":"Escalate?","condition":"severity == high OR confidence < 0.7","position":{"x":920,"y":160}}
      ],
      "edges": [
        {"id":"e1","source":"triage","target":"specialist","label":"classification"},
        {"id":"e2","source":"specialist","target":"responder","label":"findings"},
        {"id":"e3","source":"responder","target":"escalate","label":"draft"},
        {"id":"e4","source":"escalate","target":"specialist","label":"needs more info","condition":"escalate"},
        {"id":"e5","source":"escalate","target":"done","label":"send","condition":"no escalation"}
      ],
      "openclaw": {"strategy":"orchestrator-delegates","orchestrator":"triage","delegates":["specialist","responder"]}
    }'::jsonb
    ELSE graph
END
WHERE name IN ('Research Brief', 'Support Triage');
