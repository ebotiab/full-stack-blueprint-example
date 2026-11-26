"""The public demo uses real sessions and cannot alter its shared account or other sessions."""

from collections.abc import AsyncIterator

import asyncpg
import httpx
import pytest
from asgi_lifespan import LifespanManager

from my_project import demo
from my_project.api.main import create_app
from my_project.auth import sessions
from my_project.settings import PREFIX, get_settings

SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}


@pytest.fixture
async def http(
    app_settings: None, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setenv(f"{PREFIX}DEMO_ENABLED", "true")
    get_settings.cache_clear()
    app = create_app()
    async with (
        LifespanManager(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="https://test"
        ) as client,
    ):
        yield client


async def sign_in(http: httpx.AsyncClient) -> httpx.Response:
    return await http.post(
        "/api/auth/login",
        json={"email": demo.EMAIL, "password": demo.PASSWORD},
        headers=SAME_ORIGIN,
    )


async def test_visitor_reads_persisted_messages_and_ends_only_own_session(
    http: httpx.AsyncClient,
    db_conn: asyncpg.Connection,
) -> None:
    assert (await http.get("/api/messages")).status_code == 401
    login = await sign_in(http)
    assert login.status_code == 200
    assert not login.json()["is_admin"]
    assert "HttpOnly" in login.headers["set-cookie"]
    assert "Secure" in login.headers["set-cookie"]
    user_id = login.json()["id"]
    other_token = await sessions.create(db_conn, user_id)
    assert (await http.get("/api/auth/me")).json()["id"] == user_id
    messages = await http.get("/api/messages")
    assert messages.status_code == 200
    assert messages.headers["cache-control"] == "no-store"
    stored = await db_conn.fetch("SELECT text FROM messages ORDER BY id DESC LIMIT 50")
    assert [message["text"] for message in messages.json()] == [row["text"] for row in stored]
    assert (await http.post("/api/auth/logout", headers=SAME_ORIGIN)).status_code == 204
    assert (await http.get("/api/auth/me")).status_code == 401
    assert await sessions.find(db_conn, other_token) is not None


@pytest.mark.parametrize(
    "path", ["/api/auth/password", "/api/auth/logout-all", "/api/agent", "/api/messages"]
)
async def test_demo_refuses_mutations(http: httpx.AsyncClient, path: str) -> None:
    await sign_in(http)
    result = await http.post(path, json={}, headers=SAME_ORIGIN)
    assert result.status_code == 403
    assert result.headers["cache-control"] == "no-store"
    assert "read-only" in result.json()["detail"]
    assert (await http.get("/api/auth/me")).status_code == 200


async def test_demo_keeps_csrf_protection_and_bounds_login_attempts(
    http: httpx.AsyncClient,
    db_conn: asyncpg.Connection,
) -> None:
    credentials = {"email": demo.EMAIL, "password": demo.PASSWORD}
    assert (await http.post("/api/auth/login", json=credentials)).status_code == 403
    unknown = await http.post(
        "/api/auth/login",
        json={**credentials, "email": "unknown@example.com"},
        headers=SAME_ORIGIN,
    )
    assert unknown.status_code == 401
    assert await db_conn.fetchval("SELECT count(*) FROM auth_attempts") == 0
    await db_conn.execute(
        "INSERT INTO auth_attempts (key, tokens, updated_at) VALUES ($1, 0, now())",
        f"password:{demo.EMAIL}",
    )
    assert (await sign_in(http)).status_code == 429


async def test_demo_seed_is_idempotent_and_refuses_privileged_accounts(
    http: httpx.AsyncClient,
    db_conn: asyncpg.Connection,
) -> None:
    await demo.initialize(db_conn)
    await demo.initialize(db_conn)
    assert await db_conn.fetchval("SELECT count(*) FROM users") == 1
    await db_conn.execute("UPDATE users SET is_admin = true WHERE email = $1", demo.EMAIL)
    with pytest.raises(RuntimeError, match="non-administrative"):
        await demo.initialize(db_conn)
    await db_conn.execute(
        "UPDATE users SET is_admin = false, is_active = false WHERE email = $1", demo.EMAIL
    )
    with pytest.raises(RuntimeError, match="active"):
        await demo.initialize(db_conn)
