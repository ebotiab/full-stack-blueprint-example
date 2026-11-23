"""Fixtures shared by the tests."""

import os
from collections.abc import AsyncIterator, Iterator
from urllib.parse import urlsplit

import asyncpg
import pytest

from my_project.db.pool import connect
from my_project.settings import PREFIX, get_settings

#: Integration tests run against a real PostgreSQL database: `make test` and the CI set this
#: variable to a throwaway database (`<package>_test`, or `wt_<name>_test` in a git worktree:
#: scripts/db-name.sh). Without it they are skipped.
TEST_DATABASE_ENV = f"{PREFIX}TEST_DATABASE_URL"


def test_database_url() -> str | None:
    return os.environ.get(TEST_DATABASE_ENV)


@pytest.fixture
async def db_url() -> str:
    """The test database, emptied before each test."""
    url = test_database_url()
    if url is None:
        pytest.skip(f"{TEST_DATABASE_ENV} is not set")
    # This fixture empties the database: it refuses one that is not a throwaway database.
    name = urlsplit(url).path.rpartition("/")[2]
    if not name.endswith("_test"):
        pytest.fail(f"{TEST_DATABASE_ENV} must name a database ending in _test, not {name!r}")
    async with connect(url) as conn:
        await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
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
