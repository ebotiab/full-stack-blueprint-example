"""Production status read from Logfire traces (`my-project obs status`).

Answers what you ask after merging to main: which commit is deployed and since when, and which
errors happened since it arrived. Read-only: it uses a *read* token of the Logfire project, kept
outside the repository (the LOGFIRE_READ_TOKEN variable or the file ~/.config/my-project/logfire-read-token).
"""

import datetime as dt
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

PROJECT = "my-project"
SERVICE = f"{PROJECT}-api"
TOKEN_ENV = "LOGFIRE_READ_TOKEN"  # noqa: S105
TOKEN_FILE = Path.home() / ".config" / PROJECT / "logfire-read-token"
#: From this level on a record is an error (Logfire's numeric levels: 17 = error).
ERROR_LEVEL = 17
_COMMIT = re.compile(r"[0-9a-f]{7,40}")
_ENVIRONMENT = re.compile(r"[A-Za-z0-9_.-]+")

Row = dict[str, Any]


class QueryClient(Protocol):
    def query_json_rows(
        self,
        sql: str,
        *,
        min_timestamp: dt.datetime,
        limit: int | None = None,
        environment: str | list[str] | None = None,
    ) -> Any: ...


def read_token(env: Mapping[str, str] | None = None, token_file: Path = TOKEN_FILE) -> str | None:
    """The read token: the environment variable first, then the local file."""
    environ = os.environ if env is None else env
    token = environ.get(TOKEN_ENV, "").strip()
    if token:
        return token
    try:
        return token_file.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def is_commit(version: str | None, commit: str) -> bool:
    """Is `version` the requested commit? Accepts an abbreviated hash (7+ characters)."""
    wanted = commit.strip().lower()
    return bool(version) and bool(_COMMIT.fullmatch(wanted)) and str(version).startswith(wanted)


@dataclass
class Status:
    environment: str
    version: str | None
    first_seen: dt.datetime | None
    errors: list[Row]

    def summary(self) -> str:
        lines = [f"Environment: {self.environment}"]
        if self.version is None:
            lines.append(f"No traces from {SERVICE} yet.")
            return "\n".join(lines)
        lines.append(
            f"Deployed version: {self.version} (first seen {self.first_seen:%Y-%m-%d %H:%M} UTC)"
        )
        if not self.errors:
            lines.append("Errors since then: none.")
        else:
            lines.append(f"Errors since then: {len(self.errors)}")
            for row in self.errors:
                what = row.get("exception_type") or row.get("span_name") or "error"
                detail = row.get("exception_message") or row.get("message") or ""
                lines.append(f"  {row.get('start_timestamp')}  {what}: {str(detail)[:160]}")
        return "\n".join(lines)


def _parse(value: Any) -> dt.datetime | None:
    if not value:
        return None
    parsed = dt.datetime.fromisoformat(str(value))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.UTC)


def _rows(payload: Any) -> list[Row]:
    rows = payload.get("rows", []) if isinstance(payload, dict) else payload
    return [dict(row) for row in rows or []]


def fetch_status(client: QueryClient, environment: str, *, days: int = 7) -> Status:
    if not _ENVIRONMENT.fullmatch(environment):
        raise ValueError(f"Invalid environment name: {environment!r}")
    since = dt.datetime.now(dt.UTC) - dt.timedelta(days=days)
    where = f"service_name = '{SERVICE}'"
    versions = _rows(
        client.query_json_rows(
            f"SELECT service_version, min(start_timestamp) AS first_seen, "
            f"max(start_timestamp) AS last_seen FROM records WHERE {where} "
            f"GROUP BY service_version ORDER BY last_seen DESC LIMIT 1",
            min_timestamp=since,
            environment=environment,
        )
    )
    if not versions:
        return Status(environment, None, None, [])
    current = versions[0]
    first_seen = _parse(current.get("first_seen"))
    errors = _rows(
        client.query_json_rows(
            f"SELECT start_timestamp, span_name, message, exception_type, exception_message "
            f"FROM records WHERE {where} AND (is_exception OR level >= {ERROR_LEVEL}) "
            f"ORDER BY start_timestamp DESC LIMIT 20",
            min_timestamp=first_seen or since,
            environment=environment,
        )
    )
    return Status(environment, current.get("service_version"), first_seen, errors)


def wait_for_commit(
    fetch: Callable[[], Status],
    commit: str,
    *,
    minutes: float,
    sleep: Callable[[float], None],
    poll_s: float = 30.0,
) -> tuple[Status, bool]:
    """Poll until `commit` is the deployed version or `minutes` pass. Returns (status, seen)."""
    deadline = dt.datetime.now(dt.UTC) + dt.timedelta(minutes=minutes)
    while True:
        status = fetch()
        if is_commit(status.version, commit):
            return status, True
        if dt.datetime.now(dt.UTC) >= deadline:
            return status, False
        sleep(poll_s)
