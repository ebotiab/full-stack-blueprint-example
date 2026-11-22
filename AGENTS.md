# My Project

A FastAPI API with a React visor.

This file is the instructions for coding agents (Claude Code reads it through `CLAUDE.md`; Codex,
Cursor and others read it directly). People start with the [README](README.md). The project was
generated from the Copier template `full-stack-blueprint`; `.copier-answers.yml` records the
answers and is only changed by `copier update` (see "Template updates").

## Where things are

- `backend/`: the API. Python 3.14 (`.python-version`) with uv, FastAPI, asyncpg (no ORM), pydantic-settings, Typer, Logfire.
  - `src/my_project/api/`: the app (`main.py`) and its routes (`routes.py`). Every route is under `/api`.
  - `src/my_project/db/`: the connection pool (`pool.py`), the migration runner (`migrate.py`) and the SQL migrations (`migrations/NNNN_name.sql`).
  - `src/my_project/auth/`: sign-in. Accounts, sessions and API keys in PostgreSQL (`0002_auth.sql`), the `CurrentUser`/`AdminUser` dependencies (`deps.py`) and `/api/auth/*` (`routes.py`). The package docstring lists its invariants.
  - `src/my_project/settings.py`: configuration from environment variables prefixed `MY_PROJECT_`; defaults work locally.
  - `src/my_project/observability.py`: Logfire set-up and the deployed commit. `obs.py`: production status from traces.
  - `src/my_project/cli.py`: the `my-project` command (`migrate`, `users`, `api-keys`, `openapi`, `obs status`).
  - `openapi.json`: the API contract, generated (`make types`). Committed.
  - `tests/`: pytest; the integration tests use a real PostgreSQL database.
- `frontend/`: the visor. Vite, React, TypeScript, oxlint (with type-aware rules), oxfmt, Vitest, Playwright.
  - `src/api/client.ts`: the typed API client (`openapi-fetch`). `src/api/schema.d.ts` is generated from `backend/openapi.json`: never edit it.
  - `src/RequireSignIn.tsx`: the sign-in form, shown until `/api/auth/me` answers with a user; then `App`. The session cookie is HttpOnly: the visor never sees a token and never stores one.
  - `src/**/*.test.ts`: unit tests (Vitest). `e2e/`: browser tests (Playwright); they answer `/api` themselves with `page.route`.
- `Makefile`: one target per task (below). `scripts/`: what the Makefile runs (`doctor.sh`, `steps.sh`).
- `docker-compose.yml`: the local PostgreSQL 18 on port 5434.
- `.github/workflows/ci.yml`: the CI; `.github/scripts/what-changed.sh` decides which half a pull request can affect. `make check` audits the workflows with zizmor: keep `persist-credentials: false` on checkouts and pinned actions. Its `ty preview` job is informational: it never fails. `.github/dependabot.yml`: weekly grouped dependency updates.
- `render.yaml`: the Render Blueprint of the API. `backend/Dockerfile`: its image.
- `frontend/vercel.json`: the visor on Vercel; it proxies `/api` to the API, so there is no CORS.
  `x-vercel-enable-rewrite-caching: 0` keeps Vercel's CDN from caching what the proxy returns.
- `.agents/skills/`: procedures for agents (`.claude/skills` links here). `.vscode/`: editor settings that match the checks.

## Commands

Run everything from the repository root. No target asks for input; each ends with a reliable exit
code, and the multi-step ones print a summary of what passed and failed.

| Command | What it does |
| --- | --- |
| `make doctor` | Checks uv, Node and Docker; says how to fix what is missing. |
| `make setup` | Installs dependencies, starts PostgreSQL, migrates and generates the API schema and types. Safe to repeat. |
| `make dev` | Runs the API on :8000 and the visor on :5173 with reload. |
| `make check` | Everything the CI checks. Must pass before a pull request. |
| `make test` | pytest and Vitest. `make e2e` runs Playwright. |
| `make coverage` | pytest with the backend lines no test runs. A report to read, with no threshold to pass. |
| `make fmt` | Formats and auto-fixes (ruff, oxfmt). |
| `make types` | Regenerates `backend/openapi.json` and `frontend/src/api/schema.d.ts`. Run it after any API change. |
| `make migrate` | Applies pending migrations to the local database. |

Single checks while working: `cd backend && uv run pytest tests/test_api.py -k healthz`, `cd frontend && npx playwright test e2e/home.spec.ts`.

## Before opening a pull request

1. `make fmt`, then `make check`. All steps must pass; the CI runs the same targets
   (`make check-backend`, `make check-frontend`).
2. If the API changed: `make types` and commit the regenerated files. The CI fails when they are stale.
3. Commit lockfiles (`backend/uv.lock`, `frontend/package-lock.json`) whenever dependencies change.

## Conventions

- **Small pull requests.** One task per branch and per pull request, against `main`. The
  description says what changes, why, what deserves attention in review and which checks passed.
  Commit messages are one sentence that describes the result.
- **Merge on green.** When the pull request is complete (final description, nothing left to
  decide), mark it with `gh pr merge --squash --auto`: GitHub merges it as soon as the required
  checks `Backend` and `Frontend` pass, and never if they fail. If the CI fails, fix and push; the
  mark stays. If the checks already passed, `--auto` refuses ("clean status"): merge with
  `gh pr merge --squash`. This holds only while `main` requires those checks (README, "Deploy"): the
  `ship-a-change` skill looks before marking and, on an unprotected `main`, waits for the CI itself.
- **Merging is deploying.** A push to `main` deploys the API (Render waits for the CI) and the visor (Vercel). Nothing is deployed by hand.
- **Check production after merging.** A task that touches `backend/` ends when production runs the
  new commit without errors: `cd backend && uv run my-project obs status --commit <merge commit> --wait 15`
  (exit 0: deployed, no errors; 1: errors since the deploy; 2: not deployed in time; 3: no read
  token, then say so and check by hand). Investigate any error before calling the task done. Do not
  poll production with `curl` meanwhile.
- **Tests.** Every new rule or route gets a pytest test; every visible behaviour of the visor a
  Playwright test (mocking `/api`); plain logic a unit test next to it. Before finishing a
  backend change, `make coverage` lists the lines of the files you touched that no test runs: cover
  the ones that carry a rule or an error case.
- **Growing the visor.** `App.tsx` composes the page; each screen or reusable piece goes in its own
  file under `src/` (e.g. `src/messages/MessageList.tsx`), plain logic in `src/lib/` with its
  Vitest test. Data comes only through the typed `api` client, fetched in the component that shows
  it (the `useEffect` pattern in `App.tsx`, cancelled on unmount) and typed from `schema.d.ts`,
  never redeclared. Add a library only when the visor needs it, in its own pull request: a router
  (React Router) once there are several pages with their own URLs, TanStack Query once several
  components share or refresh the same data, a form library once forms need more validation than
  the browser's. Plain CSS in `src/index.css` until the project chooses a design system.
- **SQL, no ORM.** Queries are plain SQL run with asyncpg, with `$1` parameters (never string
  formatting: ruff's `S608` rejects it), next to the code that uses them; rows become Pydantic models right there. Write the
  SQL yourself and do not add an ORM or a query builder: explicit SQL is easier to review and test.
- **Migrations.** A schema change is a new file `backend/src/my_project/db/migrations/NNNN_short_name.sql`
  (next number). Never edit an applied migration: the runner stores checksums and refuses changed files.
  The runner is idempotent and takes a PostgreSQL advisory lock, so concurrent starts are safe.
  Each file runs in one transaction: a statement PostgreSQL refuses inside one (`CREATE INDEX
  CONCURRENTLY`) fails; the docstring of `db/migrate.py` says what to do instead.
- **No caching by default.** Every API response carries `Cache-Control: no-store` unless its route
  sets `Cache-Control` itself (`api/main.py`), so no shared cache serves one caller's response to
  another. Set it only on routes whose data is public; Vercel's CDN still skips the proxied `/api`
  until `frontend/vercel.json` turns `x-vercel-enable-rewrite-caching` back on for that path.
- **Sign-in.** Protect a route with a `user: CurrentUser` parameter (`AdminUser` for
  administrators) from `auth/deps.py`: 401 without credentials, 403 without permission. The
  browser sends the session cookie by itself, and scripts an API key (`Authorization: Bearer`).
  Keep the invariants in `auth/__init__.py`, which `tests/test_auth.py` checks: the session token
  never goes in JSON, tokens are stored hashed, no GET changes state, a cookie request that
  changes state passes `check_same_origin`. `0002_auth.sql` never changes: extend the tables in a
  new migration. Accounts are created with the CLI (`users create`); there is no sign-up route.
- **Configuration.** New settings go in `settings.py` with a local default and the `MY_PROJECT_` prefix,
  and in `backend/.env.example`. Secrets never enter the repository; everything runs locally without credentials.
- **No repeated work.** Read what the task needs, not every file. Run long commands (`make check`,
  Playwright) once at the end, in the background if your tool allows it, and do not spend turns
  saying they are still running.
- **Generated files.** `backend/openapi.json`, `frontend/src/api/schema.d.ts` and the lockfiles are generated:
  regenerate them, never edit them by hand.
- **Dependencies.** uv and npm only install releases that are at least 7 days old, and Dependabot
  waits as long: a compromised release is usually found and withdrawn within days. A newer version
  fails to resolve, so pick an older one. Exempting a package for an urgent fix needs the user's
  go-ahead: `exclude-newer-package = { <name> = false }` in `backend/pyproject.toml`, or
  `npm install --min-release-age=0 <name>@<version>` in `frontend/`.

## Deploy

The API runs on Render (Docker, Frankfurt, free plan) from `render.yaml`. Migrations run when it
starts (`MY_PROJECT_MIGRATE_ON_START`, on by default here): the free plan has no pre-deploy step. Production PostgreSQL is Neon (EU region). Logfire receives the traces when `LOGFIRE_TOKEN` is set. The first administrator is created with the CLI against the production database (README, "Accounts").
The one-time manual steps (accounts, secrets, variables) are in the README, "Deploy". Never create
or change cloud services without the user's explicit go-ahead.

## Template updates

The project can take later improvements of its template: with a clean worktree, run
`copier update --defaults` (add `--vcs-ref=HEAD` for the template's latest commit), resolve any
conflict markers, run `make setup` and `make check`, and open a pull request with the result.
