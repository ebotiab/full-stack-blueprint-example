"""API tests that need no database: the app is called in-process, without its lifespan."""

from __future__ import annotations

import httpx

from my_project.api.main import create_app


def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://test"
    )


async def test_healthz() -> None:
    async with client() as http:
        response = await http.get("/api/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert set(body) == {"status", "version", "commit"}


def test_openapi_lists_the_routes() -> None:
    paths = create_app().openapi()["paths"]
    assert "/api/healthz" in paths
    assert "/api/messages" in paths
