-- migrate:up
CREATE TABLE documents (
  id            bigserial PRIMARY KEY,
  filename      text NOT NULL,
  content_type  text,
  size_bytes    integer,
  sha256        text,
  extracted_text text NOT NULL,
  metadata      jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE chunks (
  id           bigserial PRIMARY KEY,
  document_id  bigint NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  chunk_index  integer NOT NULL,
  text         text NOT NULL,
  tsv          tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(text, ''))) STORED,
  created_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (document_id, chunk_index)
);

CREATE INDEX chunks_document_id_idx ON chunks(document_id);
CREATE INDEX chunks_tsv_gin_idx ON chunks USING gin(tsv);

-- migrate:down
DROP INDEX IF EXISTS chunks_tsv_gin_idx;
DROP INDEX IF EXISTS chunks_document_id_idx;
DROP TABLE IF EXISTS chunks;
DROP TABLE IF EXISTS documents;
