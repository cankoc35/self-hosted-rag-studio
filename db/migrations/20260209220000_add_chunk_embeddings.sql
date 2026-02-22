-- migrate:up
ALTER TABLE chunks
  ADD COLUMN embedding vector(768),
  ADD COLUMN embedding_model text,
  ADD COLUMN embedded_at timestamptz;

-- migrate:down
ALTER TABLE chunks
  DROP COLUMN IF EXISTS embedded_at,
  DROP COLUMN IF EXISTS embedding_model,
  DROP COLUMN IF EXISTS embedding;

