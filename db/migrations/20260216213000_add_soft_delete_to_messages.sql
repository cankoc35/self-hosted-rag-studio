-- migrate:up
-- Add soft-delete support for chat messages.
-- This keeps rows for audit/history while hiding them from active queries.

ALTER TABLE messages
ADD COLUMN IF NOT EXISTS deleted_at timestamptz;

-- Active-message index for common reads (conversation timeline queries).
CREATE INDEX IF NOT EXISTS messages_active_conversation_created_at_idx
ON messages (conversation_id, created_at)
WHERE deleted_at IS NULL;

-- migrate:down
DROP INDEX IF EXISTS messages_active_conversation_created_at_idx;

ALTER TABLE messages
DROP COLUMN IF EXISTS deleted_at;
