"""Integration tests against PostgreSQL: the migration runner and a route that reads the database."""

from __future__ import annotations

import asyncio
from pathlib import Path

import asyncpg
import httpx
import pytest
from asgi_lifespan import LifespanManager

from my_project.api.main import create_app
from my_project.db.migrate import (
    MigrationError,
    list_migrations,
    migrate,
)
from my_project.db.pool import connect

from .conftest import requires_db

pytestmark = requires_db


async def test_migrate_applies_everything_once(db_conn: asyncpg.Connection) -> None:
    versions = [m.version for m in list_migrations()]
    assert await migrate(db_conn) == versions
    assert await migrate(db_conn) == []
    assert await db_conn.fetchval("SELECT count(*) FROM schema_migrations") == len(versions)


async def test_concurrent_runners_apply_each_migration_once(db_url: str) -> None:
    async def run() -> list[str]:
        async with connect(db_url) as conn:
            return await migrate(conn)

    results = await asyncio.gather(run(), run(), run())
    applied = [version for result in results for version in result]
    assert sorted(applied) == [m.version for m in list_migrations()]


async def test_a_changed_migration_is_rejected(db_conn: asyncpg.Connection, tmp_path: Path) -> None:
    migration = tmp_path / "0001_example.sql"
    migration.write_text("CREATE TABLE example (id int);", encoding="utf-8")
    assert await migrate(db_conn, tmp_path) == ["0001_example"]
    migration.write_text("CREATE TABLE example (id bigint);", encoding="utf-8")
    with pytest.raises(MigrationError, match="0001_example"):
        await migrate(db_conn, tmp_path)


@pytest.mark.usefixtures("app_settings")
async def test_messages_come_from_the_database() -> None:
    app = create_app()
    async with (
        LifespanManager(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http,
    ):
        response = await http.get("/api/messages")
    assert response.status_code == 200
    assert [m["text"] for m in response.json()] == ["Hello from PostgreSQL"]
