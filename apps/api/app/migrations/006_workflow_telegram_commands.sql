ALTER TABLE workflows
ADD COLUMN IF NOT EXISTS telegram_command text;

CREATE UNIQUE INDEX IF NOT EXISTS idx_workflows_telegram_command
    ON workflows(telegram_command)
    WHERE telegram_command IS NOT NULL;
