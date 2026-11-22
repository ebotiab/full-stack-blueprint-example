"""Password attempts per account: a token bucket kept in PostgreSQL.

Each account starts with `CAPACITY` attempts and gets one back every `REFILL_SECONDS`. An attempt
on an empty bucket is refused without checking the password and spends nothing, so a stream of
guesses cannot keep the owner locked out longer than the refill time. It needs no Redis, so it
works on serverless functions too.
"""

import asyncpg

from .users import normalize_email

CAPACITY = 10.0
REFILL_SECONDS = 60.0

# One statement, so concurrent attempts on the same account cannot both take the last token: the
# upsert locks the row. `available` is what the bucket holds now, refilled since `updated_at`.
_TAKE = """
INSERT INTO auth_attempts AS a (key, tokens, updated_at)
VALUES ($1, $2::float8 - 1, now())
ON CONFLICT (key) DO UPDATE
SET tokens = LEAST($2::float8, a.tokens + EXTRACT(EPOCH FROM now() - a.updated_at)::float8 / $3::float8) - 1,
    updated_at = now()
WHERE LEAST($2::float8, a.tokens + EXTRACT(EPOCH FROM now() - a.updated_at)::float8 / $3::float8) >= 1
RETURNING a.tokens
"""


async def take_attempt(conn: asyncpg.Connection, email: str) -> bool:
    """Spend one password attempt of this account; False when none is left.

    Unknown emails get a bucket too: a refusal must not tell whether an account exists.
    """
    key = f"password:{normalize_email(email)}"
    left = await conn.fetchval(_TAKE, key, CAPACITY, REFILL_SECONDS)
    return left is not None


async def forget_full_buckets(conn: asyncpg.Connection) -> None:
    """Drop rows whose bucket has refilled completely: they mean the same as no row."""
    await conn.execute(
        "DELETE FROM auth_attempts WHERE updated_at < now() - make_interval(secs => $1)",
        CAPACITY * REFILL_SECONDS,
    )
