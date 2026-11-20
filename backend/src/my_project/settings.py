"""Settings read from the environment (and from backend/.env). Everything works locally without credentials."""

from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Prefix of this project's environment variables.
PREFIX = "MY_PROJECT_"
#: User, password and database name of the docker-compose PostgreSQL (make db-up).
_LOCAL_DB = "my_project"
#: The docker-compose PostgreSQL.
LOCAL_DATABASE_URL = f"postgresql://{_LOCAL_DB}:{_LOCAL_DB}@localhost:5434/{_LOCAL_DB}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix=PREFIX, env_file=".env", extra="ignore")

    #: `local`, `preview` or `production`. Logfire groups traces by it.
    environment: str = Field(
        default="local",
        validation_alias=AliasChoices(f"{PREFIX}ENVIRONMENT", "LOGFIRE_ENVIRONMENT"),
    )
    #: In production the platform (or you) sets DATABASE_URL; locally it is the docker-compose container.
    database_url: str = Field(
        default=LOCAL_DATABASE_URL,
        validation_alias=AliasChoices(f"{PREFIX}DATABASE_URL", "DATABASE_URL"),
    )
    db_pool_min_size: int = 1
    db_pool_max_size: int = 8
    #: Apply pending migrations when the API starts. On by default where the platform has no
    #: pre-deploy step (this target).
    migrate_on_start: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
