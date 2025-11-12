-- Add config column to conversations table for storing agent instructions

ALTER TABLE conversations
ADD COLUMN IF NOT EXISTS config JSONB DEFAULT '{}';

COMMENT ON COLUMN conversations.config IS 'Agent configuration including instructions, goal, and other settings';

