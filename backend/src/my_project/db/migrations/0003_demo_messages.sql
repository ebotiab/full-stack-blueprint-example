-- Fictitious, read-only example data. Migration checksums keep it stable across redeploys.
INSERT INTO messages (text) VALUES
    ('Welcome, visitor. These messages are read from the real PostgreSQL database.'),
    ('Refresh the page: your HttpOnly session cookie keeps you signed in.'),
    ('Sign out to end only your own session. No administrator access is provided.');
