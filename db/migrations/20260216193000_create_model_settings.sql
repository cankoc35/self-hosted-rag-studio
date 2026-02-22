-- migrate:up
CREATE TABLE IF NOT EXISTS model_settings (
  id                smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  generation_model  text NOT NULL,
  router_model      text NOT NULL,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);

-- Seed one global config row from current active model, fallback to a safe default.
INSERT INTO model_settings (id, generation_model, router_model)
VALUES (
  1,
  COALESCE((SELECT name FROM llm_models WHERE is_active = true LIMIT 1), 'qwen2.5:3b-instruct'),
  COALESCE((SELECT name FROM llm_models WHERE is_active = true LIMIT 1), 'qwen2.5:3b-instruct')
)
ON CONFLICT (id) DO NOTHING;

-- migrate:down
DROP TABLE IF EXISTS model_settings;
