UPDATE agents
SET tools = CASE id
    WHEN '11111111-1111-1111-1111-111111111111'::uuid THEN '["current_time","recent_messages"]'::jsonb
    WHEN '22222222-2222-2222-2222-222222222222'::uuid THEN '["current_time","recent_messages","search_messages"]'::jsonb
    WHEN '33333333-3333-3333-3333-333333333333'::uuid THEN '["current_time","recent_messages"]'::jsonb
    WHEN '44444444-4444-4444-4444-444444444444'::uuid THEN '["current_time","recent_messages","search_messages","web_search"]'::jsonb
    WHEN '55555555-5555-5555-5555-555555555555'::uuid THEN '["current_time","recent_messages"]'::jsonb
    WHEN '66666666-6666-6666-6666-666666666666'::uuid THEN '["current_time","recent_messages"]'::jsonb
    WHEN '77777777-7777-7777-7777-777777777777'::uuid THEN '["current_time","recent_messages","search_messages","web_search"]'::jsonb
    WHEN '88888888-8888-8888-8888-888888888888'::uuid THEN '["current_time","recent_messages","search_messages","web_search"]'::jsonb
    WHEN '99999999-9999-9999-9999-999999999999'::uuid THEN '["current_time","recent_messages"]'::jsonb
    ELSE tools
END
WHERE id IN (
    '11111111-1111-1111-1111-111111111111',
    '22222222-2222-2222-2222-222222222222',
    '33333333-3333-3333-3333-333333333333',
    '44444444-4444-4444-4444-444444444444',
    '55555555-5555-5555-5555-555555555555',
    '66666666-6666-6666-6666-666666666666',
    '77777777-7777-7777-7777-777777777777',
    '88888888-8888-8888-8888-888888888888',
    '99999999-9999-9999-9999-999999999999'
);
