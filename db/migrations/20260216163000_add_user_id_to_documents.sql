-- migrate:up
ALTER TABLE documents
  ADD COLUMN user_id bigint;

ALTER TABLE documents
  ADD CONSTRAINT documents_user_id_fkey
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

CREATE INDEX documents_user_id_created_at_idx
  ON documents (user_id, created_at DESC)
  WHERE user_id IS NOT NULL;

-- migrate:down
DROP INDEX IF EXISTS documents_user_id_created_at_idx;

ALTER TABLE documents
  DROP CONSTRAINT IF EXISTS documents_user_id_fkey;

ALTER TABLE documents
  DROP COLUMN IF EXISTS user_id;
