"""Accounts: create them, check a password, change it, deactivate an account."""

from typing import Any

import asyncpg
from pydantic import BaseModel

from . import passwords


class User(BaseModel):
    """A signed-in user, as routes receive it (`CurrentUser`) and `/api/auth/me` returns it."""

    id: int
    email: str
    is_admin: bool


class UserError(ValueError):
    """An account that cannot be created or found."""


def user_from_row(row: Any) -> User:
    return User(id=row["id"], email=row["email"], is_admin=row["is_admin"])


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def create_user(
    conn: asyncpg.Connection, email: str, password: str, *, is_admin: bool = False
) -> User:
    email = normalize_email(email)
    local, _, domain = email.partition("@")
    if not local or "." not in domain or len(email) > 254:
        raise UserError(f"{email!r} is not an email address.")
    passwords.check_new(password)
    password_hash = await passwords.hash_password(password)
    try:
        row = await conn.fetchrow(
            """
            INSERT INTO users (email, password_hash, is_admin) VALUES ($1, $2, $3)
            RETURNING id, email, is_admin
            """,
            email,
            password_hash,
            is_admin,
        )
    except asyncpg.UniqueViolationError:
        raise UserError(f"There is already a user with the email {email}.") from None
    return user_from_row(row)


async def find_id(conn: asyncpg.Connection, email: str) -> int:
    user_id = await conn.fetchval("SELECT id FROM users WHERE email = $1", normalize_email(email))
    if user_id is None:
        raise UserError(f"No user has the email {normalize_email(email)}.")
    return user_id


async def authenticate(conn: asyncpg.Connection, email: str, password: str) -> User | None:
    """The active user with this email and password, or None.

    An unknown email costs the same hashing work as a wrong password. A hash made with older
    parameters is replaced by one with the current ones.
    """
    row = await conn.fetchrow(
        "SELECT id, email, is_admin, password_hash FROM users WHERE email = $1 AND is_active",
        normalize_email(email),
    )
    if row is None:
        await passwords.verify_dummy(password)
        return None
    matches, new_hash = await passwords.verify(password, row["password_hash"])
    if not matches:
        return None
    if new_hash is not None:
        await conn.execute("UPDATE users SET password_hash = $2 WHERE id = $1", row["id"], new_hash)
    return user_from_row(row)


async def set_password(
    conn: asyncpg.Connection, user_id: int, password: str, *, keep_session: str | None = None
) -> None:
    """Change the password and end the user's sessions, except `keep_session` (the caller's)."""
    passwords.check_new(password)
    password_hash = await passwords.hash_password(password)
    async with conn.transaction():
        await conn.execute(
            "UPDATE users SET password_hash = $2 WHERE id = $1", user_id, password_hash
        )
        await conn.execute(
            "DELETE FROM sessions WHERE user_id = $1 AND id IS DISTINCT FROM $2::text",
            user_id,
            keep_session,
        )


async def deactivate(conn: asyncpg.Connection, user_id: int) -> None:
    """The account can no longer sign in: its sessions and API keys are deleted."""
    async with conn.transaction():
        await conn.execute("UPDATE users SET is_active = false WHERE id = $1", user_id)
        await conn.execute("DELETE FROM sessions WHERE user_id = $1", user_id)
        await conn.execute("DELETE FROM api_keys WHERE user_id = $1", user_id)
