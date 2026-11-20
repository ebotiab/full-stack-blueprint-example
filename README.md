# My Project

A FastAPI API with a React visor.

- **API**: FastAPI on Python 3.14, PostgreSQL through asyncpg with plain SQL migrations, traces in Logfire.
- **Visor**: Vite + React + TypeScript, calling the API through a client typed from its OpenAPI schema.
- **Deploy**: the API on Render, the visor on Vercel, the database on Neon.

Working with a coding agent? It reads [AGENTS.md](AGENTS.md), which has the layout, the commands
and the conventions; this README covers the same ground for people.

## Start from scratch

You need [uv](https://docs.astral.sh/uv/), [Node 24](https://nodejs.org) and [Docker](https://docs.docker.com/get-docker/). Then:

```bash
make doctor   # checks the tools and says how to fix what is missing
make setup    # installs everything, starts PostgreSQL on :5434, migrates
make dev      # API on http://127.0.0.1:8000/api, visor on http://127.0.0.1:5173
```

The API documentation is at http://127.0.0.1:8000/docs while `make dev` runs. Nothing needs
credentials locally: Logfire sends nothing without a token, and the database is the local container.
Optional local settings: `backend/.env.example` and `frontend/.env.example`.

## Everyday commands

| Command | What it does |
| --- | --- |
| `make check` | Formatting, lint, types, API contract, tests, build and Playwright: what the CI runs. |
| `make test` | pytest and Vitest; `make e2e` runs Playwright. |
| `make fmt` | Formats and auto-fixes the code. |
| `make types` | Regenerates the OpenAPI schema and the visor's API types after an API change. |
| `make migrate` | Applies new migrations (`backend/src/my_project/db/migrations/`). |
| `make help` | Lists every target. |

## Deploy

Pushing to `main` deploys; the CI must pass first. These one-time steps connect the services.
None of them is needed to develop locally.

**Database (Neon).** Create a project at https://console.neon.tech in an EU region (Frankfurt,
`aws-eu-central-1`). Copy two connection strings from "Connect": the **direct** one, and the
**pooled** one (host with `-pooler`).

**Logfire.** Create a project at https://logfire.pydantic.dev. Create a **write token** (Settings →
Write tokens) for the API's `LOGFIRE_TOKEN`, and a **read token** (Settings → Read tokens) for
`my-project obs status`: save it in `~/.config/my-project/logfire-read-token` or export it as `LOGFIRE_READ_TOKEN`. For browser errors,
create a frontend application in the project and use its restricted token as `VITE_LOGFIRE_TOKEN` in Vercel.

**API (Render).** Dashboard → New → Blueprint → this repository. Render reads `render.yaml`
(Docker, Frankfurt, free plan, health check `/api/healthz`) and asks for the secrets: `DATABASE_URL`
(Neon, direct) and `LOGFIRE_TOKEN`. Its URL will be `https://my-project-api.onrender.com` unless the name
is taken. Migrations run at start-up. The free plan sleeps after 15 idle minutes; the first request then takes about a minute.

**Visor (Vercel).** Import the repository at https://vercel.com/new with root directory
`frontend`. `frontend/vercel.json` proxies `/api` to `https://my-project-api.onrender.com`: if the API's real URL is
different, change it there. Web Analytics: turn it on in the project (no cookies).

**GitHub.** Protect `main`: require pull requests and the checks `Backend` and `Frontend`, and
allow auto-merge (Settings → General → "Allow auto-merge").

**After a deploy.** `cd backend && uv run my-project obs status --commit <sha> --wait 15` says when the commit is live
and lists any error since.

## Template updates

This project was generated with [Copier](https://copier.readthedocs.io) from `full-stack-blueprint`.
To take later improvements: commit or stash your work, run `copier update --defaults`, resolve
conflicts, then `make setup && make check`.
