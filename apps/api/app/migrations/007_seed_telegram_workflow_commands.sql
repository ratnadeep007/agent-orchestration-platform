UPDATE workflows
SET telegram_command = 'research'
WHERE name = 'Research Brief' AND telegram_command IS NULL;

UPDATE workflows
SET telegram_command = 'support'
WHERE name = 'Support Triage' AND telegram_command IS NULL;
