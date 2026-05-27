CREATE INDEX IF NOT EXISTS idx_messages_channel_external_id
    ON messages(channel, external_id)
    WHERE external_id IS NOT NULL;
