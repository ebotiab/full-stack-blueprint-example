"""Fixtures shared by the tests."""

import os
from collections.abc import AsyncIterator, Iterator
from urllib.parse import unquote, urlsplit

import asyncpg
import pytest
from pydantic_ai import models

from my_project.db.pool import connect
from my_project.settings import PREFIX, get_settings

#: No test reaches a real model: a request to one raises instead of spending. Tests use
#: Pydantic AI's TestModel or FunctionModel (pydantic_ai.models.test, .function) instead.
models.ALLOW_MODEL_REQUESTS = False

#: Integration tests run against a real PostgreSQL database: `make test` and the CI set this
#: variable to a database marked as disposable by db-up or CI. Without it they are skipped.
TEST_DATABASE_ENV = f"{PREFIX}TEST_DATABASE_URL"


def test_database_url() -> str | None:
    return os.environ.get(TEST_DATABASE_ENV)


async def reset_test_schema(conn: asyncpg.Connection, name: str) -> None:
    # Check the connected database itself. A URL or a name alone does not grant permission
    # to clear its schema. A legacy or custom database needs an explicit opt-in (README).
    disposable = await conn.fetchval(
        """
        SELECT EXISTS (
            SELECT FROM pg_catalog.pg_database
            WHERE datname = pg_catalog.current_database() AND datname = $1
              AND pg_catalog.shobj_description(oid, 'pg_database') = $2
        )
        """,
        name,
        TEST_DATABASE_ENV,
    )
    if not disposable:
        pytest.fail(f"{name!r} is not marked for {TEST_DATABASE_ENV}. See the project README.")
    await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")


@pytest.fixture
async def db_url() -> str:
    """The test database, emptied before each test."""
    url = test_database_url()
    if url is None:
        pytest.skip(f"{TEST_DATABASE_ENV} is not set")
    name = unquote(urlsplit(url).path.removeprefix("/"))
    if not name.endswith(("-test", "_test")):
        pytest.fail(f"{TEST_DATABASE_ENV} must name a disposable test database")
    async with connect(url) as conn:
        await reset_test_schema(conn, name)
    return url


@pytest.fixture
async def db_conn(db_url: str) -> AsyncIterator[asyncpg.Connection]:
    async with connect(db_url) as conn:
        yield conn


@pytest.fixture
def app_settings(db_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Point the app at the test database, migrating it at start-up, for the duration of a test."""
    monkeypatch.setenv(f"{PREFIX}DATABASE_URL", db_url)
    monkeypatch.setenv(f"{PREFIX}MIGRATE_ON_START", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
