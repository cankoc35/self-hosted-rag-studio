-- migrate:up
ALTER TABLE llm_models
  ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT false;

-- At most one active model at a time.
CREATE UNIQUE INDEX IF NOT EXISTS llm_models_one_active_idx
  ON llm_models (is_active)
  WHERE is_active = true;

-- migrate:down
DROP INDEX IF EXISTS llm_models_one_active_idx;

ALTER TABLE llm_models
  DROP COLUMN IF EXISTS is_active;
