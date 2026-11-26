# My Project

## Live demo

**[Open the live demo](https://full-stack-blueprint-example.vercel.app)** ·
**[Public API documentation](https://full-stack-blueprint-example.vercel.app/docs)**

Choose **Try the demo**, select **Read the stored messages and summarize them**, and send it.
Pydantic AI reads four fictional PostgreSQL rows and answers through Groq Free
(`openai/gpt-oss-20b`) on the US Logfire AI Gateway. Ask a follow-up and open **Inside this
response** for your timing, tool use, tokens and reported cost. Render Free can take a minute to wake up.

[How the chat works](https://full-stack-blueprint-example.vercel.app/#observability) ·
[Explore a reviewed production trace](https://full-stack-blueprint-example.vercel.app/chat-trace.html)

Each visitor session gets five attempts. Everyone shares 20 per UTC day and 100 per UTC month,
including failed runs. The chat remembers the previous exchange for 30 minutes. Signing out
ends your session. Visitor conversations are never published automatically.

A FastAPI API with a React visor.

- **API**: FastAPI on Python 3.14, PostgreSQL through asyncpg with plain SQL migrations, traces in Logfire.
- **Visor**: Vite + React + TypeScript + Tailwind CSS 4, calling the API through a client typed from its OpenAPI schema.
- **Deploy**: the API on Render, the visor on Vercel, the database on Neon.

Working with a coding agent? It reads [AGENTS.md](AGENTS.md), which has the layout, the commands
and the conventions; this README covers the same ground for people.

## Start from scratch

You need [uv](https://docs.astral.sh/uv/), [Node 26](https://nodejs.org) and [Docker](https://docs.docker.com/get-docker/). Then:

```bash
make doctor   # checks the tools and says how to fix what is missing
make setup    # installs everything, starts PostgreSQL on :5434, migrates
make dev      # API on http://127.0.0.1:8000/api, visor on http://127.0.0.1:5173
```

The API documentation is at http://127.0.0.1:8000/docs while `make dev` runs. Nothing needs
credentials locally: Logfire sends nothing without a token, and the database is the local container. The
agent (`POST /api/agent`) answers 503 until you put a model key in `backend/.env` (`ANTHROPIC_API_KEY`
for the default model, `MY_PROJECT_AI_MODEL` to change it).
Optional local settings: `backend/.env.example` and `frontend/.env.example`.
Several git worktrees of the project can run `make setup` and `make check` at the same time: they
share one local PostgreSQL. Run `bash scripts/db-name.sh` to see this checkout's development
database. Its disposable database has the same name followed by `-test`. Pytest checks the name
and the database comment before it empties the public schema. For a separately managed test
database ending in `-test` or `_test`, set its PostgreSQL database comment to
`MY_PROJECT_TEST_DATABASE_URL` only after confirming it is disposable.

When updating a project with existing worktrees, `make db-up` moves its own generated URL in
`backend/.env` to the new database name and reports the previous name. Existing databases keep
their data. To carry development data forward, dump the previous database and restore it into
the new development database before running `make setup`. Custom connection URLs are preserved.

## Everyday commands

| Command | What it does |
| --- | --- |
| `make check` | Formatting, lint, types, API contract, tests, build and Playwright: what the CI runs. |
| `make test` | pytest and Vitest; `make e2e` runs Playwright. |
| `make coverage` | The backend lines that no test runs (a report, no threshold). |
| `make fmt` | Formats and auto-fixes the code. |
| `make types` | Regenerates the OpenAPI schema and the visor's API types after an API change. |
| `make migrate` | Applies new migrations (`backend/src/my_project/db/migrations/`). |
| `make help` | Lists every target. |

## Accounts

Accounts live in the project's PostgreSQL. There is no sign-up page: create them with the CLI,
which reads the password from standard input so that it stays out of the shell's history:

```bash
cd backend
printf '%s\n' "$PASSWORD" | uv run my-project users create --email you@example.com --admin
uv run my-project api-keys create --email you@example.com --name my-script   # printed once
```

The visor shows a sign-in form until someone is signed in, and `/api/messages`, the example
route, answers only signed-in users. A browser signs in with `POST /api/auth/login` and then holds an
HttpOnly session cookie (7 days without use or 30 in total end it). Scripts send an API key as
`Authorization: Bearer <key>`.
`users set-password`, `users deactivate`, `api-keys list` and `api-keys revoke` do the rest; `--help`
explains each one. Ten wrong passwords in a row pause an account's sign-in for a minute per attempt.

## Deploy

Pushing to `main` deploys; the CI must pass first. These one-time steps connect the services.
None of them is needed to develop locally.

**Database (Neon).** Create a project at https://console.neon.tech in an EU region (Frankfurt,
`aws-eu-central-1`). Copy two connection strings from "Connect": the **direct** one, and the
**pooled** one (host with `-pooler`).

**Logfire.** Create a project at https://logfire.pydantic.dev. Create a **write token** (Settings →
Write tokens) for the API's `LOGFIRE_TOKEN`, and a **read token** (Settings → Read tokens) for
`my-project obs status`: save it in `~/.config/my-project/logfire-read-token` or export it as `LOGFIRE_READ_TOKEN`. For browser errors,
create a frontend application in the project (Frontend → Applications) and set the two values it generates in Vercel:
its restricted token as `VITE_LOGFIRE_TOKEN` and the URL of the project's region as `VITE_LOGFIRE_BASE_URL`.

**API (Render).** Dashboard → New → Blueprint → this repository. Render reads `render.yaml`
(Docker, Frankfurt, free plan, health check `/api/healthz`) and asks for the secrets: `DATABASE_URL`
(Neon, direct) and `LOGFIRE_TOKEN`. Its URL will be `https://my-project-api.onrender.com` unless the name
is taken. Migrations run at start-up. The free plan sleeps after 15 idle minutes; the first request then takes about a minute.

**Visor (Vercel).** Import the repository at https://vercel.com/new with root directory
`frontend`. `frontend/vercel.json` proxies `/api` to `https://full-stack-blueprint-example-api.onrender.com`: if the API's real URL is
different, change it there. Web Analytics: turn it on in the project (no cookies).

**Origin secret (recommended).** So that nothing reaches the API without going through Vercel,
generate a value (`python3 -c "import secrets; print(secrets.token_urlsafe(32))"`) and set it as
`ORIGIN_SECRET` in the Vercel project (Production and Preview: previews call the same API) and as
`MY_PROJECT_ORIGIN_SECRET` on the API's platform. The API then answers 403 to /api requests that did not
come through the visor's domain (`/api/healthz` excepted), so scripts call `https://<visor>/api/…`.
Without the Vercel variable, Vercel sends the literal text `$ORIGIN_SECRET`: set both or neither.

**Agent.** Set the model's key on the API's platform: `ANTHROPIC_API_KEY` for the default model, or
the variable of the provider in `MY_PROJECT_AI_MODEL`. Until then `/api/agent` answers 503. Logfire traces keep the text of questions and
answers; `MY_PROJECT_AGENT_TRACE_CONTENT=false` keeps only the metadata.

**GitHub.** Protect `main`: require pull requests and the checks `Backend` and `Frontend`, and
allow auto-merge (Settings → General → "Allow auto-merge").

**First administrator.** Once the API is deployed, create it against the production database:
`printf '%s\n' "$PASSWORD" | DATABASE_URL="<Neon direct URL>" uv run my-project users create --email … --admin` from `backend/`.

**After a deploy.** `cd backend && uv run my-project obs status --commit <sha> --wait 15` says when the commit is live
and lists any error since.

## Skills for coding agents

`.agents/skills/` (also `.claude/skills/`) gives agents the project's own procedures and links to
the skills that FastAPI, Typer, Pydantic AI and Logfire ship in their packages, so the guidance matches the
installed versions. More skills that fit this project live in other repositories; add the ones you
want with [`npx skills`](https://github.com/vercel-labs/skills) (it needs Node), which records the
commit of each in `skills-lock.json` (commit it). `--min-release-age=7` runs a release of the tool
that is at least 7 days old, as the rest of the project installs:

```bash
npx --min-release-age=7 skills add pydantic/skills --skill pydantic                # Pydantic models and validation
npx --min-release-age=7 skills add pydantic/skills --skill logfire-query           # query this project's traces
npx --min-release-age=7 skills add pydantic/skills --skill logfire-frontend        # browser errors and Web Vitals
npx --min-release-age=7 skills add microsoft/playwright-cli --skill playwright-cli # drive a browser from the agent
npx --min-release-age=7 skills add neondatabase/agent-skills --skill neon-postgres # the production database
npx --min-release-age=7 skills add render-oss/skills --skill render-deploy         # deploys on Render
```

They are read as instructions: look at what a skill says before adding it.

## Commit style

This project uses `commit_style=gitmoji` for commit subjects, PR titles and final squash
subjects. Use one Unicode emoji followed by a space and an English imperative summary,
for example `🐛 Reject expired sessions`. The small category list is in `AGENTS.md`. Keep the summary descriptive by itself.
The `ship-a-change` skill carries the final PR title into the squash commit on `main`.
This convention does not automate versions or changelogs.

To use messages without emojis, run `copier update --defaults --data commit_style=plain` from a
clean worktree; to opt into emojis, use `--data commit_style=gitmoji`. Commit the saved answer in
`.copier-answers.yml` together with the generated instructions. Later updates keep that choice.
Older projects without the answer take `gitmoji`; pass `--data commit_style=plain` on their first
update to preserve plain messages. Existing commits are never rewritten.

## Template updates

This project was generated with [Copier](https://copier.readthedocs.io) from `full-stack-blueprint`.
To take later improvements: commit or stash your work, run `copier update --defaults`, resolve
conflicts, then `make setup && make check`. The template's release notes say what each version
changes (its repository is `_src_path` in `.copier-answers.yml`).

Switching between `sessions` and database-backed `oidc` requires a data migration after either
sign-in schema has been applied. Before running setup or deploying, restore previously applied
migration files from Git and remove the newly generated, unapplied sign-in bootstrap. Write a
new forward migration that preserves account IDs and references. Rehearse account mapping,
credential enrollment or revocation, and rollback on a restored copy of the database. See
[Switching sign-in modes with existing accounts](https://github.com/ebotiab/full-stack-blueprint/blob/main/docs/choosing-your-options.md#switching-sign-in-modes-with-existing-accounts).
