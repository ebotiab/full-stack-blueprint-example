-- Counters are reserved BEFORE inference and never refunded, including on timeout/crash.
CREATE TABLE demo_chat_budget (
    period TEXT PRIMARY KEY,
    turns INTEGER NOT NULL DEFAULT 0 CHECK (turns >= 0),
    starts INTEGER NOT NULL DEFAULT 0 CHECK (starts >= 0),
    blocked_until TIMESTAMPTZ
);
CREATE TABLE demo_chat_sessions (
    session_id TEXT PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    history JSONB NOT NULL DEFAULT '[]',
    expires_at TIMESTAMPTZ NOT NULL DEFAULT now() + interval '30 minutes'
);
