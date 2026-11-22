"""Password hashing with Argon2id (pwdlib) and the rules for a new password.

Hashing takes tens of milliseconds of CPU on purpose, so it runs in a thread: the event loop keeps
serving other requests meanwhile.
"""

import asyncio
from functools import cache

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

#: Lengths of a new password, in characters. No composition rules (OWASP ASVS 6.2).
MIN_LENGTH = 8
MAX_LENGTH = 128

#: OWASP's minimum Argon2id profile: 19 MiB, 2 passes, 1 lane. Cheaper than pwdlib's default
#: (64 MiB, 3 passes, 4 lanes) on small instances and serverless functions. To make it stronger,
#: change the numbers here: `verify` rehashes each password with them at its next login.
_hasher = PasswordHash((Argon2Hasher(memory_cost=19_456, time_cost=2, parallelism=1),))


class PasswordError(ValueError):
    """A new password that breaks the rules."""


def check_new(password: str) -> None:
    if not MIN_LENGTH <= len(password) <= MAX_LENGTH:
        raise PasswordError(f"A password has {MIN_LENGTH} to {MAX_LENGTH} characters.")


async def hash_password(password: str) -> str:
    return await asyncio.to_thread(_hasher.hash, password)


async def verify(password: str, password_hash: str) -> tuple[bool, str | None]:
    """Whether the password matches, and a new hash when the stored one has older parameters."""
    return await asyncio.to_thread(_hasher.verify_and_update, password, password_hash)


@cache
def _dummy_hash() -> str:
    return _hasher.hash("no account has this password")


async def verify_dummy(password: str) -> None:
    """Do the work of a real check for an email without an account: timing does not tell them apart."""
    await asyncio.to_thread(lambda: _hasher.verify(password, _dummy_hash()))
