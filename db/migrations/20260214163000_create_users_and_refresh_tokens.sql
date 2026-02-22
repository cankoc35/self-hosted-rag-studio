-- migrate:up
CREATE TABLE users (
  id             bigserial PRIMARY KEY,
  email          text NOT NULL,
  password_hash  text NOT NULL,
  is_active      boolean NOT NULL DEFAULT true,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT users_email_not_blank CHECK (length(trim(email)) > 0)
);

-- Case-insensitive uniqueness for emails.
CREATE UNIQUE INDEX users_email_lower_uniq_idx
  ON users (lower(email));

CREATE TABLE refresh_tokens (
  id                   bigserial PRIMARY KEY,
  user_id              bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash           text NOT NULL,
  expires_at           timestamptz NOT NULL,
  revoked_at           timestamptz,
  replaced_by_token_id bigint REFERENCES refresh_tokens(id) ON DELETE SET NULL,
  created_at           timestamptz NOT NULL DEFAULT now(),
  last_used_at         timestamptz,
  user_agent           text,
  ip_address           inet,
  CONSTRAINT refresh_tokens_token_hash_not_blank CHECK (length(trim(token_hash)) > 0)
);

-- One stored row per refresh token hash.
CREATE UNIQUE INDEX refresh_tokens_token_hash_uniq_idx
  ON refresh_tokens (token_hash);

-- Fast lookup for active refresh tokens by user.
CREATE INDEX refresh_tokens_user_active_idx
  ON refresh_tokens (user_id, expires_at)
  WHERE revoked_at IS NULL;

-- Useful for cleanup jobs that purge expired/revoked tokens.
CREATE INDEX refresh_tokens_expires_at_idx
  ON refresh_tokens (expires_at);

-- migrate:down
DROP INDEX IF EXISTS refresh_tokens_expires_at_idx;
DROP INDEX IF EXISTS refresh_tokens_user_active_idx;
DROP INDEX IF EXISTS refresh_tokens_token_hash_uniq_idx;
DROP TABLE IF EXISTS refresh_tokens;

DROP INDEX IF EXISTS users_email_lower_uniq_idx;
DROP TABLE IF EXISTS users;
