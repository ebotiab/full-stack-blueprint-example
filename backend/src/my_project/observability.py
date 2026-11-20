"""Logfire instrumentation.

Without a token (LOGFIRE_TOKEN or backend/.logfire/) Logfire sends nothing and the app works the
same: `send_to_logfire="if-token-present"`. Tests never send, token or not.

The service version is the deployed commit, so traces answer "which commit runs in production
and what failed since it arrived" (`my-project obs status`).
"""

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

import logfire
from fastapi import FastAPI

from . import __version__
from .settings import Settings

#: Our own variable wins; then each platform's own variable for the deployed commit.
COMMIT_ENV_VARS = (
    "MY_PROJECT_COMMIT",
    "RENDER_GIT_COMMIT",
    "RAILWAY_GIT_COMMIT_SHA",
    "VERCEL_GIT_COMMIT_SHA",
)
#: FastAPI Cloud does not expose the commit: the deploy workflow writes it to this file
#: (backend/DEPLOYED_COMMIT) before `fastapi deploy` uploads the folder.
COMMIT_FILE = Path(__file__).resolve().parents[2] / "DEPLOYED_COMMIT"

#: Health checks are polled every few seconds: thousands of spans a day with no information.
EXCLUDED_URLS = r"/api/healthz$"

_configured = False


def deployed_commit(
    env: Mapping[str, str] | None = None, commit_file: Path = COMMIT_FILE
) -> str | None:
    """The deployed git commit, or None when running locally."""
    environ = os.environ if env is None else env
    for name in COMMIT_ENV_VARS:
        value = environ.get(name, "").strip()
        if value:
            return value
    try:
        return commit_file.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def service_version(env: Mapping[str, str] | None = None) -> str:
    """What traces carry as version: the deployed commit or, locally, the package version."""
    return deployed_commit(env) or __version__


def send_to_logfire(env: Mapping[str, str] | None = None) -> bool | Literal["if-token-present"]:
    """pytest sets PYTEST_VERSION while it runs: tests never send. The rest only with a token."""
    environ = os.environ if env is None else env
    return False if "PYTEST_VERSION" in environ else "if-token-present"


def configure_logfire(settings: Settings) -> None:
    global _configured
    if _configured:
        return
    logfire.configure(
        service_name="my-project-api",
        service_version=service_version(),
        environment=settings.environment,
        send_to_logfire=send_to_logfire(),
        console=False,
        # Public service: do not continue a caller's trace even if it sends `traceparent`.
        distributed_tracing=False,
        code_source=logfire.CodeSource(
            repository="https://github.com/ebotiab/full-stack-blueprint-example",
            revision=deployed_commit() or "main",
            root_path="backend",
        ),
    )
    logfire.instrument_asyncpg()
    _configured = True


def instrument_api(app: FastAPI) -> None:
    """One span per request, without headers and without health checks."""
    logfire.instrument_fastapi(app, capture_headers=False, excluded_urls=EXCLUDED_URLS)
