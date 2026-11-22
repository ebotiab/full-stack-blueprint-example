"""Sign-in routes under /api/auth. The session token goes in the cookie only, never in JSON."""

import asyncpg
from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from ..api.deps import ConnectionDep
from . import limits, passwords, sessions, users
from .deps import (
    CurrentSession,
    CurrentUser,
    check_same_origin,
    clear_session_cookie,
    set_session_cookie,
    unauthorized,
)
from .users import User

router = APIRouter(prefix="/auth", tags=["auth"])


class Credentials(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=passwords.MAX_LENGTH)


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=passwords.MAX_LENGTH)
    new_password: str = Field(min_length=passwords.MIN_LENGTH, max_length=passwords.MAX_LENGTH)


async def _take_attempt(conn: asyncpg.Connection, email: str) -> None:
    if not await limits.take_attempt(conn, email):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many attempts for this account. Try again in a minute.",
            headers={"Retry-After": str(int(limits.REFILL_SECONDS))},
        )


@router.post("/login")
async def login(
    credentials: Credentials, request: Request, response: Response, conn: ConnectionDep
) -> User:
    """Check email and password and start a session, held in an HttpOnly cookie."""
    check_same_origin(request)
    await _take_attempt(conn, credentials.email)
    user = await users.authenticate(conn, credentials.email, credentials.password)
    if user is None:
        raise unauthorized("Wrong email or password.")
    token = await sessions.create(conn, user.id)
    await sessions.delete_expired(conn)
    await limits.forget_full_buckets(conn)
    set_session_cookie(request, response, token)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    session: CurrentSession, request: Request, response: Response, conn: ConnectionDep
) -> None:
    """End this session."""
    await sessions.delete(conn, session.id)
    clear_session_cookie(request, response)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    session: CurrentSession, request: Request, response: Response, conn: ConnectionDep
) -> None:
    """End every session of this user, on every device, this one included."""
    await sessions.delete_for_user(conn, session.user.id)
    clear_session_cookie(request, response)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    change: PasswordChange, session: CurrentSession, conn: ConnectionDep
) -> None:
    """Change the password. The user's other sessions end; this one stays."""
    await _take_attempt(conn, session.user.email)
    if await users.authenticate(conn, session.user.email, change.current_password) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Wrong current password.")
    await users.set_password(conn, session.user.id, change.new_password, keep_session=session.id)


@router.get("/me")
async def me(user: CurrentUser) -> User:
    """The signed-in user: 401 when there is none."""
    return user
