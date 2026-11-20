"""FastAPI dependencies."""

from collections.abc import AsyncIterator
from typing import Annotated, cast

import asyncpg
from fastapi import Depends, Request

from ..db.pool import Database


async def get_connection(request: Request) -> AsyncIterator[asyncpg.Connection]:
    database: Database = request.app.state.database
    pool = await database.pool()
    async with pool.acquire() as conn:
        # The pool hands out a proxy with Connection's interface; asyncpg does not declare it so.
        yield cast(asyncpg.Connection, conn)


ConnectionDep = Annotated[asyncpg.Connection, Depends(get_connection)]
