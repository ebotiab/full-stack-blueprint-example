"""API tests that need no database: the app is called in-process, without its lifespan."""

from collections.abc import Iterator

import httpx
import pytest
from fastapi import FastAPI, Response

from my_project.api.main import create_app
from my_project.settings import PREFIX, get_settings


def client(app: FastAPI | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app or create_app()), base_url="http://test"
    )


async def test_healthz() -> None:
    async with client() as http:
        response = await http.get("/api/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert set(body) == {"status", "version", "commit"}


async def test_responses_are_not_cached_by_default() -> None:
    async with client() as http:
        response = await http.get("/api/healthz")
    assert response.headers["cache-control"] == "no-store"


async def test_a_route_can_set_its_own_cache_control() -> None:
    app = create_app()

    @app.get("/api/public")
    async def public(response: Response) -> dict[str, str]:
        response.headers["Cache-Control"] = "public, max-age=60"
        return {}

    async with client(app) as http:
        response = await http.get("/api/public")
    assert response.headers["cache-control"] == "public, max-age=60"


def test_openapi_lists_the_routes() -> None:
    paths = create_app().openapi()["paths"]
    assert "/api/healthz" in paths
    assert "/api/messages" in paths


@pytest.fixture
def origin_secret(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """The API configured with an origin secret, as when Vercel proxies it (ORIGIN_SECRET)."""
    monkeypatch.setenv(f"{PREFIX}ORIGIN_SECRET", "from-vercel")
    get_settings.cache_clear()
    yield "from-vercel"
    get_settings.cache_clear()


async def test_with_an_origin_secret_only_requests_through_vercel_reach_the_api(
    origin_secret: str,
) -> None:
    app = create_app()

    @app.get("/api/data")
    async def data() -> dict[str, str]:
        return {}

    async with client(app) as http:
        assert (await http.get("/api/data")).status_code == 403
        wrong = {"x-origin-secret": "guessed"}
        assert (await http.get("/api/data", headers=wrong)).status_code == 403
        right = {"x-origin-secret": origin_secret}
        assert (await http.get("/api/data", headers=right)).status_code == 200
        # The platform's health check and the docs need no secret.
        assert (await http.get("/api/healthz")).status_code == 200
        assert (await http.get("/openapi.json")).status_code == 200
