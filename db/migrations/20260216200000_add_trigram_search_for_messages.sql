-- migrate:up
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Trigram index on normalized message content for fuzzy search.
CREATE INDEX IF NOT EXISTS messages_content_trgm_idx
  ON messages
  USING gin (lower(content) gin_trgm_ops);

-- Fast path for user conversation listing by recency.
CREATE INDEX IF NOT EXISTS conversations_user_updated_idx
  ON conversations (user_id, updated_at DESC, id DESC);

-- migrate:down
DROP INDEX IF EXISTS conversations_user_updated_idx;
DROP INDEX IF EXISTS messages_content_trgm_idx;
DROP EXTENSION IF EXISTS pg_trgm;
