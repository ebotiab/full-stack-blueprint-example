"""Browser sessions: a row per signed-in browser, found by the token in its cookie."""

import datetime as dt
from dataclasses import dataclass

import asyncpg

from . import tokens
from .users import User, user_from_row

#: A session ends after this long without requests (OWASP ASVS 7.3.1)...
IDLE_TIMEOUT = dt.timedelta(days=7)
#: ...and this long after sign-in, used or not (ASVS 7.3.2). The cookie lasts as long.
MAX_AGE = dt.timedelta(days=30)
#: `last_seen_at` is written at most this often, not on every request.
TOUCH_INTERVAL = dt.timedelta(hours=1)


@dataclass(frozen=True)
class Session:
    id: str
    user: User


async def create(conn: asyncpg.Connection, user_id: int) -> str:
    """Start a session and return its token, for the cookie only."""
    token = tokens.new_token()
    await conn.execute(
        "INSERT INTO sessions (id, secret_hash, user_id) VALUES ($1, $2, $3)",
        token.id,
        token.secret_hash,
        user_id,
    )
    return token.value


async def find(conn: asyncpg.Connection, token: str) -> Session | None:
    """The live session of an active user that this token proves, or None."""
    parts = tokens.split(token)
    if parts is None:
        return None
    session_id, secret = parts
    row = await conn.fetchrow(
        """
        SELECT s.secret_hash, s.last_seen_at, u.id, u.email, u.is_admin
        FROM sessions s JOIN users u ON u.id = s.user_id
        WHERE s.id = $1 AND u.is_active
          AND s.last_seen_at > now() - $2::interval
          AND s.created_at > now() - $3::interval
        """,
        session_id,
        IDLE_TIMEOUT,
        MAX_AGE,
    )
    if row is None or not tokens.secret_matches(secret, row["secret_hash"]):
        return None
    if row["last_seen_at"] < dt.datetime.now(dt.UTC) - TOUCH_INTERVAL:
        await conn.execute("UPDATE sessions SET last_seen_at = now() WHERE id = $1", session_id)
    return Session(session_id, user_from_row(row))


async def delete(conn: asyncpg.Connection, session_id: str) -> None:
    await conn.execute("DELETE FROM sessions WHERE id = $1", session_id)


async def delete_for_user(conn: asyncpg.Connection, user_id: int) -> None:
    await conn.execute("DELETE FROM sessions WHERE user_id = $1", user_id)


async def delete_expired(conn: asyncpg.Connection) -> None:
    """Remove sessions that can no longer be used. Login calls it: no scheduled job is needed."""
    await conn.execute(
        "DELETE FROM sessions WHERE last_seen_at < now() - $1::interval"
        " OR created_at < now() - $2::interval",
        IDLE_TIMEOUT,
        MAX_AGE,
    )
