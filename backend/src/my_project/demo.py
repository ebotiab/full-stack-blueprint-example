"""The public example's read-only visitor account. These credentials are deliberately public.

Opt in with MY_PROJECT_DEMO_ENABLED. This module belongs to the example, not the template.
Do not enable it on a database containing private data.
"""

import asyncpg
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint

from .auth import users
from .settings import get_settings

EMAIL = "visitor@example.com"
PASSWORD = "Explore-the-blueprint!"  # noqa: S105 - deliberately public, non-admin demo credentials


async def initialize(conn: asyncpg.Connection) -> None:
    """Seed once, including during concurrent starts, without changing an existing account."""
    async with conn.transaction():
        await conn.execute("SELECT pg_advisory_xact_lock(824602611)")
        existing = await conn.fetchrow(
            "SELECT is_admin, is_active FROM users WHERE email = $1", EMAIL
        )
        if existing is None:
            await users.create_user(conn, EMAIL, PASSWORD)
        elif existing["is_admin"] or not existing["is_active"]:
            raise RuntimeError("The public visitor account must be active and non-administrative.")


async def read_only(request: Request, call_next: RequestResponseEndpoint) -> Response:
    """Limit the entire public deployment to reading data and individual session sign-in/out.

    The shared visitor must never change its password or end other visitors' sessions.
    Only the separately authenticated, quota-limited chat may call a read-only agent tool.
    """
    if (
        get_settings().demo_enabled
        and request.method not in {"GET", "HEAD", "OPTIONS"}
        and request.url.path
        not in {
            "/api/auth/login",
            "/api/auth/logout",
            "/api/demo-chat",
        }
    ):
        return JSONResponse({"detail": "This public demo is read-only."}, 403)
    return await call_next(request)
