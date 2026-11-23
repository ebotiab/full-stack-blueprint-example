"""`obs status` logic, with a fake Logfire client (no network, no token), and what is traced."""

import datetime as dt
import json
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI
from logfire.testing import CaptureLogfire
from pydantic import BaseModel

from my_project import obs
from my_project.observability import (
    deployed_commit,
    instrument_api,
)
from my_project.settings import PREFIX


class FakeClient:
    def __init__(self, *answers: list[dict[str, Any]]) -> None:
        self.answers = list(answers)
        self.queries: list[str] = []

    def query_json_rows(
        self,
        sql: str,
        *,
        min_timestamp: dt.datetime,
        limit: int | None = None,
        environment: str | list[str] | None = None,
    ) -> Any:
        self.queries.append(sql)
        return {"columns": [], "rows": self.answers.pop(0)}


def test_status_reports_the_deployed_version_and_its_errors() -> None:
    client = FakeClient(
        [{"service_version": "abc1234def", "first_seen": "2026-11-18T10:00:00Z"}],
        [
            {
                "start_timestamp": "2026-11-18T10:05:00Z",
                "exception_type": "ValueError",
                "exception_message": "boom",
            }
        ],
    )
    status = obs.fetch_status(client, "production")
    assert status.version == "abc1234def"
    assert status.first_seen == dt.datetime(2026, 11, 18, 10, tzinfo=dt.UTC)
    assert "ValueError: boom" in status.summary()


def test_status_without_traces() -> None:
    status = obs.fetch_status(FakeClient([]), "production")
    assert status.version is None
    assert "No traces" in status.summary()


def test_wait_for_commit_stops_when_the_commit_shows_up() -> None:
    versions = iter(["old0000", "old0000", "abc1234def"])
    sleeps: list[float] = []

    def fetch() -> obs.Status:
        return obs.Status("production", next(versions), None, [])

    status, seen = obs.wait_for_commit(fetch, "abc1234", minutes=5, sleep=sleeps.append)
    assert seen
    assert status.version == "abc1234def"
    assert len(sleeps) == 2


def test_read_token_prefers_the_environment(tmp_path: Path) -> None:
    token_file = tmp_path / "token"
    token_file.write_text("from-file\n", encoding="utf-8")
    assert obs.read_token({obs.TOKEN_ENV: "from-env"}, token_file) == "from-env"
    assert obs.read_token({}, token_file) == "from-file"
    assert obs.read_token({}, tmp_path / "missing") is None


def test_deployed_commit_reads_our_variable_then_the_platforms(tmp_path: Path) -> None:
    missing = tmp_path / "DEPLOYED_COMMIT"
    assert deployed_commit({}, missing) is None
    assert deployed_commit({"RAILWAY_GIT_COMMIT_SHA": "r1"}, missing) == "r1"
    both = {f"{PREFIX}COMMIT": "own", "RENDER_GIT_COMMIT": "r2"}
    assert deployed_commit(both, missing) == "own"
    missing.write_text("f1\n", encoding="utf-8")
    assert deployed_commit({}, missing) == "f1"


class ResetBody(BaseModel):
    email: str
    code: str


async def test_requests_are_traced_without_their_arguments(capfire: CaptureLogfire) -> None:
    """Neither a request's body nor its signed-in user reaches Logfire; a validation error does,
    without the value that was sent."""
    app = FastAPI()

    @app.post("/reset")
    async def reset(body: ResetBody) -> None: ...

    instrument_api(app)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        await http.post("/reset", json={"email": "ada@example.com", "code": "ABCD-EFGH"})
        await http.post("/reset", json={"email": "ada@example.com"})
    spans = capfire.exporter.exported_spans_as_dict()
    traced = json.dumps([span["attributes"] for span in spans], default=str)
    assert "fastapi.arguments.errors" in traced
    assert "ada@example.com" not in traced
    assert "ABCD-EFGH" not in traced
