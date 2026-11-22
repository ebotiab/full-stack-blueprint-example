-- Accounts, browser sessions, API keys and login attempts (auth/). Never edit this file: the
-- runner refuses an applied migration that changed. Extend or fix the tables in a new migration.

-- Emails are stored lower-case (auth/users.py normalizes them), so UNIQUE ignores case.
CREATE TABLE users (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email TEXT NOT NULL UNIQUE CHECK (email = lower(email)),
    password_hash TEXT NOT NULL,
    is_admin BOOLEAN NOT NULL DEFAULT false,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- A session and an API key are a token `<id>.<secret>` held by the client: only the SHA-256 of
-- the secret is stored, so a copy of the database does not let anyone in.
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    secret_hash BYTEA NOT NULL,
    user_id BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX sessions_user_id_idx ON sessions (user_id);

CREATE TABLE api_keys (
    id TEXT PRIMARY KEY,
    secret_hash BYTEA NOT NULL,
    user_id BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at TIMESTAMPTZ
);
CREATE INDEX api_keys_user_id_idx ON api_keys (user_id);

-- One token bucket per account: password attempts left and when the row last changed.
CREATE TABLE auth_attempts (
    key TEXT PRIMARY KEY,
    tokens DOUBLE PRECISION NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
