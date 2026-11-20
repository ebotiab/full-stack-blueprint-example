"""The My Project API. Every route lives under /api, so the visor and the API can share a domain."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import logfire
from fastapi import FastAPI

from .. import __version__
from ..db.migrate import migrate
from ..db.pool import Database, connect
from ..observability import configure_logfire, instrument_api
from ..settings import get_settings
from . import routes


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings = get_settings()
    database: Database = app.state.database
    if settings.migrate_on_start:
        async with connect(settings.database_url) as conn:
            applied = await migrate(conn)
        logfire.info("migrations applied at start-up: {applied}", applied=applied)
    await database.pool()
    # One record per start: tells from when this version serves, even if nobody called it yet.
    logfire.info("api started")
    try:
        yield
    finally:
        await database.close()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logfire(settings)
    app = FastAPI(
        title="My Project API",
        version=__version__,
        description="A FastAPI API with a React visor.",
        lifespan=lifespan,
    )
    app.state.database = Database(
        settings.database_url,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
    )
    instrument_api(app)
    app.include_router(routes.router, prefix="/api")
    return app


app = create_app()
