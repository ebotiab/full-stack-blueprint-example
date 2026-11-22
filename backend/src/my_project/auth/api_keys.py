"""API keys: long-lived credentials for scripts and other services (`Authorization: Bearer`).

Each key belongs to a user and acts as that user. The CLI creates, lists and revokes them; the key
itself is shown once, at creation.
"""

import datetime as dt
from dataclasses import dataclass

import asyncpg

from . import tokens
from .users import User, user_from_row

#: `last_used_at` is written at most this often, not on every request.
TOUCH_INTERVAL = dt.timedelta(hours=1)


@dataclass(frozen=True)
class ApiKey:
    id: str
    name: str
    created_at: dt.datetime
    last_used_at: dt.datetime | None


async def create(conn: asyncpg.Connection, user_id: int, name: str) -> str:
    """Create a key and return it. Only its hash is stored: it cannot be shown again."""
    token = tokens.new_token()
    await conn.execute(
        "INSERT INTO api_keys (id, secret_hash, user_id, name) VALUES ($1, $2, $3, $4)",
        token.id,
        token.secret_hash,
        user_id,
        name,
    )
    return token.value


async def find_user(conn: asyncpg.Connection, key: str) -> User | None:
    """The active user this key belongs to, or None for an unknown or revoked key."""
    parts = tokens.split(key)
    if parts is None:
        return None
    key_id, secret = parts
    row = await conn.fetchrow(
        """
        SELECT k.secret_hash, k.last_used_at, u.id, u.email, u.is_admin
        FROM api_keys k JOIN users u ON u.id = k.user_id
        WHERE k.id = $1 AND u.is_active
        """,
        key_id,
    )
    if row is None or not tokens.secret_matches(secret, row["secret_hash"]):
        return None
    last_used = row["last_used_at"]
    if last_used is None or last_used < dt.datetime.now(dt.UTC) - TOUCH_INTERVAL:
        await conn.execute("UPDATE api_keys SET last_used_at = now() WHERE id = $1", key_id)
    return user_from_row(row)


async def list_for_user(conn: asyncpg.Connection, user_id: int) -> list[ApiKey]:
    rows = await conn.fetch(
        "SELECT id, name, created_at, last_used_at FROM api_keys WHERE user_id = $1 ORDER BY created_at",
        user_id,
    )
    return [ApiKey(row["id"], row["name"], row["created_at"], row["last_used_at"]) for row in rows]


async def revoke(conn: asyncpg.Connection, key_id: str) -> bool:
    """Delete a key; False when no key has this id."""
    deleted = await conn.fetchval("DELETE FROM api_keys WHERE id = $1 RETURNING id", key_id)
    return deleted is not None
