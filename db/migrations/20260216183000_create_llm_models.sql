-- migrate:up
CREATE TABLE llm_models (
  id          bigserial PRIMARY KEY,
  name        text NOT NULL UNIQUE,
  is_enabled  boolean NOT NULL DEFAULT true,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

-- Fast path for "enabled models" UI listing.
CREATE INDEX llm_models_enabled_name_idx
  ON llm_models (name)
  WHERE is_enabled;

-- Initial allowlist (from LLM-MODELS.txt, deduplicated).
INSERT INTO llm_models (name) VALUES
  ('llama3.1:8b'),
  ('llama3.2:8b'),
  ('mistral:7b'),
  ('deepseek-r1:8b'),
  ('deepseek-coder:6.7b'),
  ('phi4-mini'),
  ('phi3:medium'),
  ('phi3:mini'),
  ('qwen2.5:7b'),
  ('qwen2.5:coder:7b'),
  ('gemma2:9b'),
  ('gemma2:2b'),
  ('mixtral:8x7b-q2_K'),
  ('qwen3:8b'),
  ('qwen3:14b'),
  ('qwen2.5:14b'),
  ('lfm2.5-thinking:latest'),
  ('glm-4.7-flash:latest')
ON CONFLICT (name) DO NOTHING;

-- migrate:down
DROP INDEX IF EXISTS llm_models_enabled_name_idx;
DROP TABLE IF EXISTS llm_models;
