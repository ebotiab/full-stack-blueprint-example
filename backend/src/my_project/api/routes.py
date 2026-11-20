"""Example routes. Replace /api/messages with your own; keep /api/healthz for the platform."""

import datetime as dt

from fastapi import APIRouter
from pydantic import BaseModel

from .. import __version__
from ..observability import deployed_commit
from .deps import ConnectionDep

router = APIRouter()


class Health(BaseModel):
    status: str
    version: str
    commit: str | None


class Message(BaseModel):
    id: int
    text: str
    created_at: dt.datetime


@router.get("/healthz", tags=["system"])
async def healthz() -> Health:
    """Liveness check for the platform; it does not touch the database."""
    return Health(status="ok", version=__version__, commit=deployed_commit())


@router.get("/messages", tags=["messages"])
async def list_messages(conn: ConnectionDep) -> list[Message]:
    """Messages from the database, newest first."""
    rows = await conn.fetch("SELECT id, text, created_at FROM messages ORDER BY id DESC LIMIT 50")
    return [Message(**dict(row)) for row in rows]
