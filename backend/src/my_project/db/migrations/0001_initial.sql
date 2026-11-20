-- First migration: an example table that the API reads (GET /api/messages).
-- Replace it with your own schema in 0002_*.sql and later files; never edit an applied migration.
CREATE TABLE messages (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO messages (text) VALUES ('Hello from PostgreSQL');
