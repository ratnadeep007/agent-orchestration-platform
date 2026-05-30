UPDATE agents
SET tools = CASE id
    WHEN '44444444-4444-4444-4444-444444444444'::uuid THEN '["current_time","recent_messages","search_messages","web_search"]'::jsonb
    WHEN '77777777-7777-7777-7777-777777777777'::uuid THEN '["current_time","recent_messages","search_messages","web_search"]'::jsonb
    WHEN '88888888-8888-8888-8888-888888888888'::uuid THEN '["current_time","recent_messages","search_messages","web_search"]'::jsonb
    ELSE tools
END
WHERE id IN (
    '44444444-4444-4444-4444-444444444444',
    '77777777-7777-7777-7777-777777777777',
    '88888888-8888-8888-8888-888888888888'
);
