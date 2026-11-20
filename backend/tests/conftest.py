from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator

import asyncpg
import pytest

from my_project.db.pool import connect
from my_project.settings import PREFIX, get_settings

#: Integration tests run against a real PostgreSQL database: `make test` and the CI set this
#: variable to a throwaway database (`my_project_test`). Without it they are skipped.
TEST_DATABASE_ENV = f"{PREFIX}TEST_DATABASE_URL"


def test_database_url() -> str | None:
    return os.environ.get(TEST_DATABASE_ENV)


requires_db = pytest.mark.skipif(
    test_database_url() is None,
    reason=f"set {TEST_DATABASE_ENV} to run the PostgreSQL integration tests (make test does)",
)


@pytest.fixture
async def db_url() -> AsyncIterator[str]:
    """The test database, emptied before each test."""
    url = test_database_url()
    if url is None:
        pytest.skip(f"{TEST_DATABASE_ENV} is not set")
    async with connect(url) as conn:
        await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    yield url


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
