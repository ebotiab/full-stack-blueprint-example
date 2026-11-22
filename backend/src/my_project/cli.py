"""`my-project` command line: database migrations, accounts, API keys, OpenAPI schema and production status."""

import asyncio
import json
import sys
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Annotated

import asyncpg
import typer

app = typer.Typer(help=__doc__, no_args_is_help=True)
obs_app = typer.Typer(help="Production status from Logfire traces.", no_args_is_help=True)
app.add_typer(obs_app, name="obs")
users_app = typer.Typer(help="Accounts. Passwords come from standard input.", no_args_is_help=True)
app.add_typer(users_app, name="users")
keys_app = typer.Typer(help="API keys: `Authorization: Bearer <key>`.", no_args_is_help=True)
app.add_typer(keys_app, name="api-keys")


def _with_connection[T](work: Callable[[asyncpg.Connection], Awaitable[T]]) -> T:
    """Run `work` with a connection to the configured database (DATABASE_URL)."""
    from .db.pool import connect
    from .settings import get_settings

    async def go() -> T:
        async with connect(get_settings().database_url) as conn:
            return await work(conn)

    return asyncio.run(go())


@app.command()
def migrate() -> None:
    """Apply pending SQL migrations (idempotent; safe to run from several processes)."""
    from .db.migrate import migrate as run_migrations

    applied = _with_connection(run_migrations)
    typer.echo(f"Applied: {', '.join(applied)}" if applied else "Database is up to date.")


EmailOption = Annotated[str, typer.Option(help="The account's email.")]


def _password_from_stdin() -> str:
    """The first line of standard input. An option would stay in the shell's history."""
    if sys.stdin.isatty():
        typer.echo("Pipe the password in: printf '%s\\n' \"$PASSWORD\" | ...", err=True)
        raise typer.Exit(2)
    return sys.stdin.readline().removesuffix("\n")


def _fail(error: ValueError) -> typer.Exit:
    typer.echo(str(error), err=True)
    return typer.Exit(1)


@users_app.command("create")
def users_create(
    email: EmailOption,
    admin: Annotated[bool, typer.Option(help="Make the user an administrator.")] = False,
) -> None:
    """Create an account with the password from standard input."""
    from .auth import users

    password = _password_from_stdin()
    try:
        user = _with_connection(
            lambda conn: users.create_user(conn, email, password, is_admin=admin)
        )
    except ValueError as error:
        raise _fail(error) from None
    role = "administrator" if user.is_admin else "user"
    typer.echo(f"Created {role} {user.email} (id {user.id}).")


@users_app.command("set-password")
def users_set_password(email: EmailOption) -> None:
    """Replace a password with the one from standard input and end the user's sessions."""
    from .auth import users

    password = _password_from_stdin()

    async def work(conn: asyncpg.Connection) -> None:
        await users.set_password(conn, await users.find_id(conn, email), password)

    try:
        _with_connection(work)
    except ValueError as error:
        raise _fail(error) from None
    typer.echo(f"New password set; {email} is signed out everywhere.")


@users_app.command("deactivate")
def users_deactivate(email: EmailOption) -> None:
    """Stop an account from signing in: its sessions and API keys are deleted."""
    from .auth import users

    async def work(conn: asyncpg.Connection) -> None:
        await users.deactivate(conn, await users.find_id(conn, email))

    try:
        _with_connection(work)
    except ValueError as error:
        raise _fail(error) from None
    typer.echo(f"Deactivated {email}.")


@keys_app.command("create")
def api_keys_create(
    email: EmailOption,
    name: Annotated[str, typer.Option(help="What the key is for, e.g. `nightly-import`.")],
) -> None:
    """Create a key that acts as this user. It is printed once, alone on standard output."""
    from .auth import api_keys, users

    async def work(conn: asyncpg.Connection) -> str:
        return await api_keys.create(conn, await users.find_id(conn, email), name)

    try:
        key = _with_connection(work)
    except ValueError as error:
        raise _fail(error) from None
    typer.echo(key)
    typer.echo("Store it now: it cannot be shown again.", err=True)


@keys_app.command("list")
def api_keys_list(email: EmailOption) -> None:
    """The user's keys: id, name, creation and last use (never the key itself)."""
    from .auth import api_keys, users

    async def work(conn: asyncpg.Connection) -> list[api_keys.ApiKey]:
        return await api_keys.list_for_user(conn, await users.find_id(conn, email))

    try:
        keys = _with_connection(work)
    except ValueError as error:
        raise _fail(error) from None
    for key in keys:
        used = f"{key.last_used_at:%Y-%m-%d %H:%M}" if key.last_used_at else "never"
        typer.echo(f"{key.id}  {key.name}  created {key.created_at:%Y-%m-%d}  last used {used}")


@keys_app.command("revoke")
def api_keys_revoke(
    key_id: Annotated[str, typer.Option("--id", help="The key's id: the part before the dot.")],
) -> None:
    """Delete a key: requests with it get 401 from now on."""
    from .auth import api_keys

    if not _with_connection(lambda conn: api_keys.revoke(conn, key_id)):
        typer.echo(f"No API key has the id {key_id}.", err=True)
        raise typer.Exit(1)
    typer.echo(f"Revoked {key_id}.")


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
