-- migrate:up
ALTER TABLE documents
  ADD COLUMN deleted_at timestamptz NULL;

-- Fast path for user-scoped active document listing.
CREATE INDEX documents_user_id_active_created_at_idx
  ON documents (user_id, created_at DESC)
  WHERE user_id IS NOT NULL AND deleted_at IS NULL;

-- Optional global active-document scans.
CREATE INDEX documents_active_created_at_idx
  ON documents (created_at DESC)
  WHERE deleted_at IS NULL;

-- migrate:down
DROP INDEX IF EXISTS documents_active_created_at_idx;
DROP INDEX IF EXISTS documents_user_id_active_created_at_idx;

ALTER TABLE documents
  DROP COLUMN IF EXISTS deleted_at;
