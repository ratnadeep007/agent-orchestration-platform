UPDATE workflow_templates
SET graph = jsonb_set(graph, '{nodes,1,reply}', 'true'::jsonb, true)
WHERE name = 'Research Brief';

UPDATE workflow_templates
SET graph = jsonb_set(graph, '{nodes,2,reply}', 'true'::jsonb, true)
WHERE name = 'Support Triage';

UPDATE workflows
SET graph = jsonb_set(graph, '{nodes,1,reply}', 'true'::jsonb, true)
WHERE name = 'Research Brief';

UPDATE workflows
SET graph = jsonb_set(graph, '{nodes,2,reply}', 'true'::jsonb, true)
WHERE name = 'Support Triage';
