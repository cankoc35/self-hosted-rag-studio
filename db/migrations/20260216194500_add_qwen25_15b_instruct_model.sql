-- migrate:up
INSERT INTO llm_models (name)
VALUES ('qwen2.5:1.5b-instruct')
ON CONFLICT (name) DO NOTHING;

-- migrate:down
DELETE FROM llm_models
WHERE name = 'qwen2.5:1.5b-instruct';
