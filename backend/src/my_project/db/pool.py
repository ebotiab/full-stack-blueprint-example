"""PostgreSQL connections with asyncpg (no ORM: SQL lives next to the code that runs it)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import asyncpg

#: Parameters that some providers put in their connection strings and asyncpg does not understand:
#: it would send them to the server as session settings and the connection would fail.
_FOREIGN_PARAMS = frozenset({"channel_binding"})

#: Seconds an idle connection is kept. Serverless databases (Neon) suspend after five idle minutes
#: and would close older connections from their side.
_MAX_IDLE_S = 120.0


def normalize_dsn(dsn: str) -> str:
    """Drop the connection-string parameters asyncpg rejects; everything else is unchanged."""
    parts = urlsplit(dsn)
    if not parts.query:
        return dsn
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    kept = [(key, value) for key, value in pairs if key not in _FOREIGN_PARAMS]
    if len(kept) == len(pairs):
        return dsn
    return urlunsplit(parts._replace(query=urlencode(kept)))


async def _init_connection(conn: asyncpg.Connection) -> None:
    for typename in ("json", "jsonb"):
        await conn.set_type_codec(
            typename, encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
        )


class Database:
    """A pool created on first use and closed with the app.

    Long-running servers create it in the lifespan; serverless functions may serve a request
    before (or without) a lifespan, so `pool()` also creates it lazily.
    """

    def __init__(self, dsn: str, *, min_size: int = 1, max_size: int = 8) -> None:
        self._dsn = normalize_dsn(dsn)
        self._min_size = min_size
        self._max_size = max_size
        self._pool: asyncpg.Pool | None = None
        self._lock = asyncio.Lock()

    async def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            async with self._lock:
                if self._pool is None:
                    self._pool = await asyncpg.create_pool(
                        self._dsn,
                        min_size=self._min_size,
                        max_size=self._max_size,
                        init=_init_connection,
                        command_timeout=60,
                        max_inactive_connection_lifetime=_MAX_IDLE_S,
                    )
        return self._pool

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None


@asynccontextmanager
async def connect(dsn: str) -> AsyncGenerator[asyncpg.Connection]:
    """A single connection, for the CLI and tests."""
    conn = await asyncpg.connect(normalize_dsn(dsn))
    try:
        await _init_connection(conn)
        yield conn
    finally:
        await conn.close()
