"""Settings read from the environment (and from backend/.env). Everything works locally without credentials."""

from functools import lru_cache
from typing import Annotated

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

#: Prefix of this project's environment variables.
PREFIX = "MY_PROJECT_"
#: User, password and database name of the docker-compose PostgreSQL (make db-up).
_LOCAL_DB = "my_project"
#: The docker-compose PostgreSQL. A git worktree has its own database there, which `make db-up`
#: writes to the worktree's backend/.env (scripts/db-name.sh).
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
    #: Public read-only example with a shared non-admin visitor account. Never use with private data.
    demo_enabled: bool = False
    #: Activate only after verifying a dedicated free BYOK route, telemetry and its limits.
    demo_chat_enabled: bool = False
    #: Exact project-specific Gateway Connect route; never a URL or a fallback endpoint.
    demo_gateway_route: str = Field(default="", pattern=r"^[a-z0-9-]*$")
    #: Apply pending migrations when the API starts. On by default where the platform has no
    #: pre-deploy step (this target).
    migrate_on_start: bool = True
    #: The value Vercel adds as `x-origin-secret` to every /api request it proxies
    #: (frontend/vercel.json, from the Vercel variable ORIGIN_SECRET). When set, the API refuses
    #: /api requests without it: only the visor's domain reaches the API. Empty: not checked.
    origin_secret: str = ""
    #: The agent's model (agent/), as Pydantic AI names it: `provider:model`. Its key is the
    #: provider's own variable: ANTHROPIC_API_KEY, OPENAI_API_KEY, or PYDANTIC_AI_GATEWAY_API_KEY for
    #: `gateway/…` models. Without it, /api/agent answers 503.
    ai_model: str = "anthropic:claude-opus-5-5"
    #: Whether Logfire traces keep the text of questions and answers. Without sign-in the route is
    #: public, so visitors' text reaches the traces: set it to false if that must not happen.
    agent_trace_content: bool = True
    #: The visor's origins, comma-separated (`https://my-app.vercel.app`). Only browsers that do not
    #: send `Sec-Fetch-Site` (from before 2023) need them: see `auth/deps.py`, `check_same_origin`.
    auth_public_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    @field_validator("auth_public_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
