"""Opaque tokens for sessions and API keys: `<id>.<secret>`, both parts random.

The id finds the row; the secret (256 bits) proves the token. The database keeps only the
SHA-256 of the secret, compared in constant time. A fast hash is enough here, unlike passwords:
the secret is random, so there is nothing to guess.
"""

import hashlib
import hmac
import secrets
from typing import NamedTuple

#: Longer values are refused before any query: real tokens have about 60 characters.
_MAX_LENGTH = 100


class NewToken(NamedTuple):
    id: str
    secret_hash: bytes
    #: What the client keeps (the cookie, the API key). It is never stored.
    value: str


def new_token() -> NewToken:
    # token_urlsafe uses letters, digits, `-` and `_`: never the `.` that separates the parts.
    token_id = secrets.token_urlsafe(12)
    secret = secrets.token_urlsafe(32)
    return NewToken(token_id, hash_secret(secret), f"{token_id}.{secret}")


def split(value: str) -> tuple[str, str] | None:
    """The id and the secret of a token, or None when it does not have that shape."""
    if len(value) > _MAX_LENGTH:
        return None
    token_id, _, secret = value.partition(".")
    if not token_id or not secret:
        return None
    return token_id, secret


def hash_secret(secret: str) -> bytes:
    return hashlib.sha256(secret.encode()).digest()


def secret_matches(secret: str, secret_hash: bytes) -> bool:
    return hmac.compare_digest(hash_secret(secret), secret_hash)
