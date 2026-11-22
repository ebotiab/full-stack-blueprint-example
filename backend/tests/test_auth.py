"""Sign-in against a real PostgreSQL database: every invariant of `auth/` has a test here."""

import asyncio
import hashlib
from collections.abc import AsyncIterator

import asyncpg
import httpx
import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from typer.testing import CliRunner

from my_project.api.main import create_app
from my_project.auth import (
    api_keys,
    limits,
    users,
)
from my_project.auth.deps import (
    AdminUser,
    CurrentUser,
)
from my_project.cli import app as cli
from my_project.db.migrate import migrate
from my_project.settings import PREFIX, get_settings

EMAIL = "ada@example.com"
PASSWORD = "correct horse battery staple"
NEW_PASSWORD = "a different long password"
COOKIE = "__Host-session"
#: What a browser sends with a request from the visor's own page.
SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}


@pytest.fixture
async def conn(db_conn: asyncpg.Connection) -> asyncpg.Connection:
    await migrate(db_conn)
    return db_conn


@pytest.fixture
async def user(conn: asyncpg.Connection) -> users.User:
    return await users.create_user(conn, EMAIL, PASSWORD)


@pytest.fixture
def app(app_settings: None) -> FastAPI:
    return create_app()


@pytest.fixture
async def http(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """A client over https, as in production, where the session cookie is Secure."""
    transport = httpx.ASGITransport(app=app)
    async with (
        LifespanManager(app),
        httpx.AsyncClient(transport=transport, base_url="https://test") as client,
    ):
        yield client


async def login(
    http: httpx.AsyncClient, email: str = EMAIL, password: str = PASSWORD
) -> httpx.Response:
    credentials = {"email": email, "password": password}
    return await http.post("/api/auth/login", json=credentials, headers=SAME_ORIGIN)


def bearer(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


async def test_login_sets_the_cookie_and_stores_only_a_hash(
    http: httpx.AsyncClient, user: users.User, conn: asyncpg.Connection
) -> None:
    response = await login(http)
    assert response.status_code == 200
    assert response.json() == {"id": user.id, "email": EMAIL, "is_admin": False}
    name, _, rest = response.headers["set-cookie"].partition("=")
    token, *attributes = rest.split("; ")
    assert name == COOKIE
    assert set(attributes) == {"HttpOnly", "Max-Age=2592000", "Path=/", "SameSite=lax", "Secure"}
    assert token not in response.text
    secret = token.partition(".")[2]
    stored = await conn.fetchval("SELECT secret_hash FROM sessions")
    assert stored == hashlib.sha256(secret.encode()).digest()

    me = await http.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == EMAIL
    assert me.headers["cache-control"] == "no-store"


async def test_an_unknown_email_and_a_wrong_password_get_the_same_answer(
    http: httpx.AsyncClient, user: users.User
) -> None:
    unknown = await login(http, email="nobody@example.com")
    wrong = await login(http, password="not the password")
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()
    assert "set-cookie" not in wrong.headers


async def test_me_needs_credentials(http: httpx.AsyncClient) -> None:
    response = await http.get("/api/auth/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


async def test_logout_deletes_the_session(
    http: httpx.AsyncClient, user: users.User, conn: asyncpg.Connection
) -> None:
    await login(http)
    token = http.cookies[COOKIE]
    response = await http.post("/api/auth/logout", headers=SAME_ORIGIN)
    assert response.status_code == 204
    assert COOKIE not in http.cookies
    assert await conn.fetchval("SELECT count(*) FROM sessions") == 0
    reused = await http.get("/api/auth/me", headers={"Cookie": f"{COOKIE}={token}"})
    assert reused.status_code == 401


EXPIRE = {
    "idle for 8 days": "UPDATE sessions SET last_seen_at = now() - interval '8 days'",
    "started 31 days ago": "UPDATE sessions SET created_at = now() - interval '31 days'",
}


@pytest.mark.parametrize("statement", list(EXPIRE.values()), ids=list(EXPIRE))
async def test_an_expired_session_is_refused(
    http: httpx.AsyncClient, user: users.User, conn: asyncpg.Connection, statement: str
) -> None:
    await login(http)
    await conn.execute(statement)
    assert (await http.get("/api/auth/me")).status_code == 401


async def test_last_seen_is_written_at_most_hourly(
    http: httpx.AsyncClient, user: users.User, conn: asyncpg.Connection
) -> None:
    await login(http)
    await conn.execute("UPDATE sessions SET last_seen_at = now() - interval '30 minutes'")
    await http.get("/api/auth/me")
    assert await conn.fetchval("SELECT last_seen_at < now() - interval '29 minutes' FROM sessions")
    await conn.execute("UPDATE sessions SET last_seen_at = now() - interval '2 hours'")
    await http.get("/api/auth/me")
    assert await conn.fetchval("SELECT last_seen_at > now() - interval '1 minute' FROM sessions")


CROSS_SITE = {
    "no headers": {},
    "cross-site": {"Sec-Fetch-Site": "cross-site"},
    "same-site": {"Sec-Fetch-Site": "same-site"},
    "unlisted origin": {"Origin": "https://attacker.example"},
}


@pytest.mark.parametrize("headers", list(CROSS_SITE.values()), ids=list(CROSS_SITE))
async def test_a_cookie_request_from_another_site_is_refused(
    http: httpx.AsyncClient, user: users.User, conn: asyncpg.Connection, headers: dict[str, str]
) -> None:
    await login(http)
    response = await http.post("/api/auth/logout", headers=headers)
    assert response.status_code == 403
    assert await conn.fetchval("SELECT count(*) FROM sessions") == 1


async def test_login_from_another_site_is_refused(
    http: httpx.AsyncClient, user: users.User
) -> None:
    credentials = {"email": EMAIL, "password": PASSWORD}
    response = await http.post("/api/auth/login", json=credentials)
    assert response.status_code == 403


async def test_an_old_browser_passes_with_a_listed_origin(
    http: httpx.AsyncClient, user: users.User, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(f"{PREFIX}AUTH_PUBLIC_ORIGINS", "https://visor.example, https://b.example")
    get_settings.cache_clear()
    await login(http)
    response = await http.post("/api/auth/logout", headers={"Origin": "https://visor.example"})
    assert response.status_code == 204


async def test_an_api_key_acts_as_its_user_without_origin_checks(
    app: FastAPI, http: httpx.AsyncClient, user: users.User, conn: asyncpg.Connection
) -> None:
    @app.post("/api/test/write")
    async def write(caller: CurrentUser) -> dict[str, str]:
        return {"email": caller.email}

    key = await api_keys.create(conn, user.id, "test")
    response = await http.post("/api/test/write", headers=bearer(key))
    assert response.status_code == 200
    assert response.json() == {"email": EMAIL}
    secret = key.partition(".")[2]
    stored = await conn.fetchval("SELECT secret_hash FROM api_keys")
    assert stored == hashlib.sha256(secret.encode()).digest()


async def test_a_revoked_api_key_is_refused(
    http: httpx.AsyncClient, user: users.User, conn: asyncpg.Connection
) -> None:
    key = await api_keys.create(conn, user.id, "test")
    assert (await http.get("/api/auth/me", headers=bearer(key))).status_code == 200
    assert await api_keys.revoke(conn, key.partition(".")[0])
    assert (await http.get("/api/auth/me", headers=bearer(key))).status_code == 401


async def test_a_deactivated_user_is_signed_out_everywhere(
    http: httpx.AsyncClient, user: users.User, conn: asyncpg.Connection
) -> None:
    await login(http)
    key = await api_keys.create(conn, user.id, "test")
    await users.deactivate(conn, user.id)
    assert (await http.get("/api/auth/me")).status_code == 401
    assert (await http.get("/api/auth/me", headers=bearer(key))).status_code == 401
    assert (await login(http)).status_code == 401


async def test_a_new_password_ends_the_other_sessions(
    http: httpx.AsyncClient, user: users.User
) -> None:
    await login(http)
    other = http.cookies[COOKIE]
    await login(http)
    change = {"current_password": PASSWORD, "new_password": NEW_PASSWORD}
    response = await http.post("/api/auth/password", json=change, headers=SAME_ORIGIN)
    assert response.status_code == 204
    assert (await http.get("/api/auth/me")).status_code == 200
    stale = await http.get("/api/auth/me", headers={"Cookie": f"{COOKIE}={other}"})
    assert stale.status_code == 401
    assert (await login(http)).status_code == 401
    assert (await login(http, password=NEW_PASSWORD)).status_code == 200


async def test_a_new_password_needs_the_current_one(
    http: httpx.AsyncClient, user: users.User
) -> None:
    await login(http)
    change = {"current_password": "not the password", "new_password": NEW_PASSWORD}
    response = await http.post("/api/auth/password", json=change, headers=SAME_ORIGIN)
    assert response.status_code == 400


async def test_a_hash_with_older_parameters_is_replaced_at_login(
    http: httpx.AsyncClient, conn: asyncpg.Connection
) -> None:
    weaker = PasswordHash((Argon2Hasher(memory_cost=8_192, time_cost=1, parallelism=1),))
    await conn.execute(
        "INSERT INTO users (email, password_hash) VALUES ($1, $2)", EMAIL, weaker.hash(PASSWORD)
    )
    assert (await login(http)).status_code == 200
    assert "m=19456,t=2,p=1" in str(await conn.fetchval("SELECT password_hash FROM users"))


async def test_too_many_attempts_are_refused_for_a_while(
    http: httpx.AsyncClient, user: users.User
) -> None:
    for _ in range(int(limits.CAPACITY)):
        assert (await login(http, password="not the password")).status_code == 401
    response = await login(http)
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"


async def test_messages_need_a_signed_in_user(http: httpx.AsyncClient, user: users.User) -> None:
    assert (await http.get("/api/messages")).status_code == 401
    await login(http)
    assert (await http.get("/api/messages")).status_code == 200


async def test_admin_routes_refuse_other_users(
    app: FastAPI, http: httpx.AsyncClient, user: users.User, conn: asyncpg.Connection
) -> None:
    @app.get("/api/test/admin")
    async def admin_only(admin: AdminUser) -> dict[str, str]:
        return {"email": admin.email}

    await login(http)
    assert (await http.get("/api/test/admin")).status_code == 403
    await conn.execute("UPDATE users SET is_admin = true")
    assert (await http.get("/api/test/admin")).status_code == 200


async def test_local_development_gets_a_cookie_without_secure(
    app: FastAPI, user: users.User
) -> None:
    transport = httpx.ASGITransport(app=app)
    async with (
        LifespanManager(app),
        httpx.AsyncClient(transport=transport, base_url="http://localhost:8000") as local,
    ):
        response = await login(local)
        assert response.headers["set-cookie"].startswith("session=")
        assert "Secure" not in response.headers["set-cookie"]
        assert (await local.get("/api/auth/me")).status_code == 200


def test_openapi_describes_the_auth_routes_and_schemes() -> None:
    schema = create_app().openapi()
    assert {"/api/auth/login", "/api/auth/logout", "/api/auth/me"} <= set(schema["paths"])
    assert set(schema["components"]["securitySchemes"]) == {"session", "apiKey"}


def test_the_cli_manages_accounts_and_api_keys(app_settings: None) -> None:
    runner = CliRunner()
    assert runner.invoke(cli, ["migrate"]).exit_code == 0
    create = ["users", "create", "--email", EMAIL, "--admin"]
    created = runner.invoke(cli, create, input=f"{PASSWORD}\n")
    assert created.exit_code == 0, created.output
    assert runner.invoke(cli, create, input=f"{PASSWORD}\n").exit_code == 1
    short = ["users", "create", "--email", "grace@example.com"]
    assert runner.invoke(cli, short, input="short\n").exit_code == 1

    made = runner.invoke(cli, ["api-keys", "create", "--email", EMAIL, "--name", "nightly"])
    assert made.exit_code == 0, made.output
    key = made.stdout.strip()

    async def me() -> httpx.Response:
        app = create_app()
        transport = httpx.ASGITransport(app=app)
        async with (
            LifespanManager(app),
            httpx.AsyncClient(transport=transport, base_url="https://test") as http,
        ):
            return await http.get("/api/auth/me", headers=bearer(key))

    assert asyncio.run(me()).json()["is_admin"] is True
    key_id = key.partition(".")[0]
    listed = runner.invoke(cli, ["api-keys", "list", "--email", EMAIL]).stdout
    assert f"{key_id}  nightly" in listed
    assert runner.invoke(cli, ["api-keys", "revoke", "--id", key_id]).exit_code == 0
    assert runner.invoke(cli, ["api-keys", "revoke", "--id", key_id]).exit_code == 1

    new_password = runner.invoke(cli, ["users", "set-password", "--email", EMAIL], input="x" * 12)
    assert new_password.exit_code == 0, new_password.output
    assert runner.invoke(cli, ["users", "deactivate", "--email", EMAIL]).exit_code == 0
    unknown = ["users", "deactivate", "--email", "nobody@example.com"]
    assert runner.invoke(cli, unknown).exit_code == 1
