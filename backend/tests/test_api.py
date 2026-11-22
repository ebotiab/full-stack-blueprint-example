"""API tests that need no database: the app is called in-process, without its lifespan."""

import httpx
from fastapi import FastAPI, Response

from my_project.api.main import create_app


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
