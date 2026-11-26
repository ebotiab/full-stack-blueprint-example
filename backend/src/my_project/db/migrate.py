"""SQL migrations: numbered files in `migrations/`, each applied once, in order.

`migrate()` is idempotent and safe to run from several processes at once: it holds a PostgreSQL
advisory lock while it works, so a second runner waits and then finds nothing pending. Each file
runs in its own transaction together with its row in `schema_migrations`, so a statement that
PostgreSQL refuses inside a transaction (`CREATE INDEX CONCURRENTLY`, `VACUUM`) fails here: create
the index without `CONCURRENTLY`, or build it by hand on the production database first and write
the migration as `CREATE INDEX IF NOT EXISTS`. An applied file must not change afterwards (its
checksum is stored): write a new migration instead.

Run it with `my-project migrate` (or `make migrate`).
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

import asyncpg

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

#: Advisory lock key: a fixed 64-bit number derived from the package name.
_LOCK_NAME = b"my_project:migrations"
LOCK_KEY = int.from_bytes(hashlib.sha256(_LOCK_NAME).digest()[:8], signed=True)


class MigrationError(RuntimeError):
    """An applied migration changed, or a migration failed."""


@dataclass(frozen=True)
class Migration:
    version: str
    path: Path

    @property
    def sql(self) -> str:
        return self.path.read_text(encoding="utf-8")

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.sql.encode()).hexdigest()


def list_migrations(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    return [Migration(path.stem, path) for path in sorted(directory.glob("*.sql"))]


async def _ensure_table(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            checksum TEXT NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


async def migrate(conn: asyncpg.Connection, directory: Path = MIGRATIONS_DIR) -> list[str]:
    """Apply pending migrations and return their versions (empty when up to date)."""
    await conn.execute("SELECT pg_advisory_lock($1)", LOCK_KEY)
    try:
        await _ensure_table(conn)
        rows = await conn.fetch("SELECT version, checksum FROM schema_migrations")
        applied = {row["version"]: row["checksum"] for row in rows}
        migrations = list_migrations(directory)
        # Copier replaces the bootstrap file when switching sign-in modes. Its replacement
        # also creates users. An intentional conversion restores the old migration history
        # and supplies its own forward migration before deploying the new application.
        versions = {migration.version for migration in migrations}
        old = "0002_oidc_users"
        new = "0002_auth"
        if old in applied and old not in versions and new in versions and new not in applied:
            raise MigrationError(
                f"Sign-in migration {old} was applied, but {new} replaces it and creates "
                "users again. Restore the original migration and write an explicit account "
                "conversion before applying pending migrations. See README, 'Template updates'."
            )
        done: list[str] = []
        for migration in migrations:
            checksum = applied.get(migration.version)
            if checksum is not None:
                if checksum != migration.checksum:
                    raise MigrationError(
                        f"Migration {migration.version} changed after it was applied. "
                        "Restore the file and add a new migration instead."
                    )
                continue
            async with conn.transaction():
                await conn.execute(migration.sql)
                await conn.execute(
                    "INSERT INTO schema_migrations (version, checksum) VALUES ($1, $2)",
                    migration.version,
                    migration.checksum,
                )
            done.append(migration.version)
        return done
    finally:
        await conn.execute("SELECT pg_advisory_unlock($1)", LOCK_KEY)
