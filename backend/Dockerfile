# API image for Render. Built from backend/ (the service's root directory).
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_DEV=1 PYTHONUNBUFFERED=1

# Dependencies first, so code changes reuse this layer.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-install-project

COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked

# The API runs as an unprivileged user: at run time it only reads /app.
RUN useradd --system --no-create-home --uid 10001 app
USER app

ENV PATH="/app/.venv/bin:$PATH" PORT=8000
EXPOSE 8000
# Pending migrations run when the API starts (MY_PROJECT_MIGRATE_ON_START, on by default for
# this target): Render's free plan has no pre-deploy command.
# uvicorn directly: the image only has production dependencies, not the `fastapi` CLI.
CMD ["sh", "-c", "exec uvicorn my_project.api.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
