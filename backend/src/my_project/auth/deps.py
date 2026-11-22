"""Who is calling: FastAPI dependencies that protect routes.

    @router.get("/things")
    async def list_things(user: CurrentUser, conn: ConnectionDep) -> list[Thing]: ...

`CurrentUser` accepts the session cookie (the visor) or an API key in `Authorization: Bearer`
(scripts); `AdminUser` also requires `is_admin`; `CurrentSession` only the cookie. Without valid
credentials the answer is 401, without permission 403.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response, Security, status
from fastapi.requests import HTTPConnection
from fastapi.security import APIKeyCookie, HTTPAuthorizationCredentials, HTTPBearer

from ..api.deps import ConnectionDep
from ..settings import get_settings
from . import api_keys, sessions
from .sessions import Session
from .users import User

#: The session cookie. With the `__Host-` prefix the browser only keeps it if it is Secure, for
#: Path=/ and without Domain: no other host (a sibling subdomain, plain http) can set or replace it.
COOKIE_NAME = "__Host-session"
#: On http://localhost (`make dev`) the cookie cannot be Secure in every browser (Safari drops
#: it), so local development uses this name, without Secure.
LOCAL_COOKIE_NAME = "session"
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def is_local(request: HTTPConnection) -> bool:
    return request.url.scheme == "http" and request.url.hostname in _LOCAL_HOSTS


def cookie_name(request: HTTPConnection) -> str:
    return LOCAL_COOKIE_NAME if is_local(request) else COOKIE_NAME


def set_session_cookie(request: Request, response: Response, token: str) -> None:
    response.set_cookie(
        cookie_name(request),
        token,
        max_age=int(sessions.MAX_AGE.total_seconds()),
        path="/",
        secure=not is_local(request),
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(request: Request, response: Response) -> None:
    response.delete_cookie(
        cookie_name(request), path="/", secure=not is_local(request), httponly=True, samesite="lax"
    )


class SessionCookie(APIKeyCookie):
    """The session cookie under `cookie_name(request)`; declared so that OpenAPI describes it."""

    async def __call__(self, request: HTTPConnection) -> str | None:
        return request.cookies.get(cookie_name(request))


session_cookie = SessionCookie(name=COOKIE_NAME, scheme_name="session", auto_error=False)
api_key_bearer = HTTPBearer(scheme_name="apiKey", auto_error=False)


def unauthorized(detail: str = "Not signed in.") -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"}
    )


def check_same_origin(request: Request) -> None:
    """Refuse a state-changing request that another site may have made the browser send (CSRF).

    Browsers mark every request with `Sec-Fetch-Site`: it must be `same-origin`. One that does not
    send it (before 2023) must send an `Origin` listed in the `AUTH_PUBLIC_ORIGINS` setting.
    Safe methods never change state, so they pass; API keys never come from a browser on their
    own, so requests with them skip this check.
    """
    if request.method in _SAFE_METHODS:
        return
    site = request.headers.get("sec-fetch-site")
    if site == "same-origin":
        return
    if site is None and request.headers.get("origin") in get_settings().auth_public_origins:
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Cross-site request refused.")


async def current_session(
    request: Request,
    conn: ConnectionDep,
    token: Annotated[str | None, Security(session_cookie)],
) -> Session:
    if token is not None:
        check_same_origin(request)
        session = await sessions.find(conn, token)
        if session is not None:
            return session
    raise unauthorized()


async def current_user(
    request: Request,
    conn: ConnectionDep,
    token: Annotated[str | None, Security(session_cookie)],
    bearer: Annotated[HTTPAuthorizationCredentials | None, Security(api_key_bearer)],
) -> User:
    if bearer is not None:
        user = await api_keys.find_user(conn, bearer.credentials)
        if user is None:
            raise unauthorized("Unknown or revoked API key.")
        return user
    session = await current_session(request, conn, token)
    return session.user


CurrentSession = Annotated[Session, Depends(current_session)]
CurrentUser = Annotated[User, Depends(current_user)]


async def require_admin(user: CurrentUser) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrators only.")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
