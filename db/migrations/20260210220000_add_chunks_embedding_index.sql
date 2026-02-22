-- migrate:up
-- Speed up vector similarity search on chunks.embedding (cosine distance).
-- Uses an approximate nearest neighbor (ANN) index (HNSW).
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw_cosine_idx
  ON chunks
  USING hnsw (embedding vector_cosine_ops)
  WHERE embedding IS NOT NULL;

-- migrate:down
DROP INDEX IF EXISTS chunks_embedding_hnsw_cosine_idx;

