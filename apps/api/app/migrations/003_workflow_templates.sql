INSERT INTO workflow_templates (name, description, graph)
SELECT name, description, graph::jsonb
FROM (
    VALUES
    (
        'Research Brief',
        'Researcher gathers facts, writer drafts a concise brief, reviewer sends feedback until ready.',
        '{
          "nodes": [
            {"id":"researcher","type":"agent","label":"Researcher","role":"Collect facts","position":{"x":80,"y":120}},
            {"id":"writer","type":"agent","label":"Writer","role":"Draft brief","position":{"x":360,"y":120}},
            {"id":"reviewer","type":"agent","label":"Reviewer","role":"Check quality","position":{"x":640,"y":120}},
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
        }'
    ),
    (
        'Support Triage',
        'Triage agent classifies request, specialist investigates, responder drafts reply with escalation loop.',
        '{
          "nodes": [
            {"id":"triage","type":"agent","label":"Triage","role":"Classify request","position":{"x":80,"y":160}},
            {"id":"specialist","type":"agent","label":"Specialist","role":"Investigate issue","position":{"x":360,"y":160}},
            {"id":"responder","type":"agent","label":"Responder","role":"Draft response","position":{"x":640,"y":160}},
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
        }'
    )
) AS templates(name, description, graph)
WHERE NOT EXISTS (
    SELECT 1 FROM workflow_templates WHERE workflow_templates.name = templates.name
);
