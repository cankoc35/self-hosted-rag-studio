-- migrate:up
ALTER TABLE conversations
  ADD COLUMN user_id bigint;

ALTER TABLE conversations
  ADD CONSTRAINT conversations_user_id_fkey
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

CREATE INDEX conversations_user_id_updated_at_idx
  ON conversations (user_id, updated_at DESC)
  WHERE user_id IS NOT NULL;

-- migrate:down
DROP INDEX IF EXISTS conversations_user_id_updated_at_idx;

ALTER TABLE conversations
  DROP CONSTRAINT IF EXISTS conversations_user_id_fkey;

ALTER TABLE conversations
  DROP COLUMN IF EXISTS user_id;
