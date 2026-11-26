"""The My Project API. Every route lives under /api, so the visor and the API can share a domain."""

import hmac
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import logfire
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from .. import __version__, demo
from ..agent import routes as agent_routes
from ..auth import routes as auth_routes
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
    if settings.demo_enabled:
        async with connect(settings.database_url) as conn:
            await demo.initialize(conn)
    # One record per start: tells from when this version serves, even if nobody called it yet.
    logfire.info("api started")
    try:
        yield
    finally:
        await database.close()


async def no_store_by_default(request: Request, call_next: RequestResponseEndpoint) -> Response:
    """Responses carry `Cache-Control: no-store` unless their route sets `Cache-Control` itself.

    A shared cache between the API and its clients (Vercel's CDN on a proxied `/api`, any proxy)
    must never keep a response that depends on who asked and serve it to someone else. A route
    whose data is public and may be cached sets the header itself, e.g. `public, max-age=60`.
    """
    response = await call_next(request)
    response.headers.setdefault("Cache-Control", "no-store")
    return response


async def only_through_vercel(request: Request, call_next: RequestResponseEndpoint) -> Response:
    """With `ORIGIN_SECRET` set, /api answers only requests that came through the visor's domain.

    Vercel adds the secret as `x-origin-secret` to every request it proxies to /api, replacing any
    value the client sent (frontend/vercel.json). A request straight to the API's own URL lacks
    it and gets 403, so nothing can skip Vercel (its firewall, its logs). `/api/healthz` stays
    open for the platform's health checks, and so do the docs outside /api.
    """
    secret = get_settings().origin_secret
    path = request.url.path
    if secret and path.startswith("/api/") and path != "/api/healthz":
        given = request.headers.get("x-origin-secret", "")
        if not hmac.compare_digest(given.encode(), secret.encode()):
            return JSONResponse({"detail": "Use the API through the visor's domain."}, 403)
    return await call_next(request)


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
    app.add_middleware(BaseHTTPMiddleware, dispatch=demo.read_only)
    app.add_middleware(BaseHTTPMiddleware, dispatch=only_through_vercel)
    app.add_middleware(BaseHTTPMiddleware, dispatch=no_store_by_default)
    app.include_router(routes.router, prefix="/api")
    app.include_router(agent_routes.router, prefix="/api")
    app.include_router(auth_routes.router, prefix="/api")
    return app


app = create_app()
