-- migrate:up
CREATE TABLE conversations (
  id                bigserial PRIMARY KEY,
  conversation_key  text NOT NULL UNIQUE,
  metadata          jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE messages (
  id               bigserial PRIMARY KEY,
  conversation_id  bigint NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role             text NOT NULL CHECK (role IN ('system', 'user', 'assistant')),
  content          text NOT NULL,
  sources          jsonb NOT NULL DEFAULT '[]'::jsonb,
  metadata         jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX messages_conversation_id_created_at_idx
  ON messages(conversation_id, created_at);

-- migrate:down
DROP INDEX IF EXISTS messages_conversation_id_created_at_idx;
DROP TABLE IF EXISTS messages;
DROP TABLE IF EXISTS conversations;
