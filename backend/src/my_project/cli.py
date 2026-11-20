"""`my-project` command line: database migrations, OpenAPI schema and production status."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(help=__doc__, no_args_is_help=True)
obs_app = typer.Typer(help="Production status from Logfire traces.", no_args_is_help=True)
app.add_typer(obs_app, name="obs")


@app.command()
def migrate() -> None:
    """Apply pending SQL migrations (idempotent; safe to run from several processes)."""
    from .db.migrate import migrate as run_migrations
    from .db.pool import connect
    from .settings import get_settings

    async def go() -> list[str]:
        async with connect(get_settings().database_url) as conn:
            return await run_migrations(conn)

    applied = asyncio.run(go())
    typer.echo(f"Applied: {', '.join(applied)}" if applied else "Database is up to date.")


@app.command()
def openapi(
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="File to write; stdout when omitted.")
    ] = None,
) -> None:
    """Write the API's OpenAPI schema without starting a server."""
    from .api.main import app as api

    text = json.dumps(api.openapi(), indent=2, ensure_ascii=False) + "\n"
    if output is None:
        typer.echo(text, nl=False)
    else:
        output.write_text(text, encoding="utf-8")
        typer.echo(f"Wrote {output}")


@obs_app.command("status")
def obs_status(
    environment: Annotated[str, typer.Option(help="Logfire environment to read.")] = "production",
    commit: Annotated[
        str | None, typer.Option(help="Wait until this commit is the deployed version.")
    ] = None,
    wait: Annotated[float, typer.Option(help="Minutes to wait for --commit.")] = 15.0,
) -> None:
    """Which commit is deployed and which errors happened since it arrived.

    Exit codes: 0 deployed and no errors, 1 errors since the deploy, 2 the commit did not show up
    in time, 3 no read token.
    """
    from logfire.query_client import LogfireQueryClient

    from . import obs

    token = obs.read_token()
    if token is None:
        typer.echo(
            f"No Logfire read token: set {obs.TOKEN_ENV} or write it to {obs.TOKEN_FILE}.", err=True
        )
        raise typer.Exit(3)
    with LogfireQueryClient(read_token=token) as client:

        def fetch() -> obs.Status:
            return obs.fetch_status(client, environment)

        if commit is None:
            status, seen = fetch(), True
        else:
            status, seen = obs.wait_for_commit(fetch, commit, minutes=wait, sleep=time.sleep)
    typer.echo(status.summary())
    if not seen:
        typer.echo(f"Commit {commit} is not the deployed version after {wait:g} minutes.", err=True)
        raise typer.Exit(2)
    if status.errors:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
