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
  - `src/my_project/agent/`: an LLM agent built with Pydantic AI. The agent, its tools and the limits of one run in `assistant.py`; the model from `MY_PROJECT_AI_MODEL` in `model.py`; `POST /api/agent` in `routes.py`.
  - `src/my_project/observability.py`: Logfire set-up and the deployed commit. `obs.py`: production status from traces.
  - `src/my_project/cli.py`: the `my-project` command (`migrate`, `users`, `api-keys`, `openapi`, `obs status`).
  - `openapi.json`: the API contract, generated (`make types`). Committed.
  - `tests/`: pytest; the integration tests use a real PostgreSQL database.
- `frontend/`: the visor. Vite, React, TypeScript, Tailwind CSS 4 (Vite plugin, theme in `src/index.css`), oxlint (with type-aware rules), oxfmt, Vitest, Playwright.
  - `src/api/client.ts`: the typed API client (`openapi-fetch`). `src/api/schema.d.ts` is generated from `backend/openapi.json`: never edit it.
  - `src/RequireSignIn.tsx`: the sign-in form, shown until `/api/auth/me` answers with a user; then `App`. The session cookie is HttpOnly: the visor never sees a token and never stores one.
  - `src/**/*.test.ts`: unit tests (Vitest). `e2e/`: browser tests (Playwright); they answer `/api` themselves with `page.route`.
- `Makefile`: one target per task (below). `scripts/`: what the Makefile runs (`doctor.sh`, `steps.sh`, `db-name.sh`).
- `docker-compose.yml`: the local PostgreSQL 18 on port 5434, one Compose project (`my-project`) shared by every checkout of the repository.
- `.github/workflows/ci.yml`: the CI; `.github/scripts/what-changed.sh` decides which half a pull request can affect. `make check` audits the workflows with zizmor: keep `persist-credentials: false` on checkouts and pinned actions. Its `ty preview` job is informational: it never fails. `.github/dependabot.yml`: weekly grouped dependency updates.
- `render.yaml`: the Render Blueprint of the API. `backend/Dockerfile`: its image.
- `frontend/vercel.json`: the visor on Vercel; it proxies `/api` to the API, so there is no CORS.
  `x-vercel-enable-rewrite-caching: 0` keeps Vercel's CDN from caching what the proxy returns.
  Its `routes` rule adds `x-origin-secret` (Vercel variable ORIGIN_SECRET) to every proxied request;
  with `MY_PROJECT_ORIGIN_SECRET` set to the same value, the API answers 403 to /api requests that skip
  Vercel (`api/main.py`, `only_through_vercel`). Scripts then call the API at the visor's domain.
- `.agents/skills/`: skills for agents (`.claude/skills` links here). The project's own procedures
  (`change-the-api`, `ship-a-change`) are directories; `fastapi`, `typer`,
  `building-pydantic-ai-agents`, `logfire-evals`, `logfire-gateway` and
  `logfire-instrumentation` are links to the skills those libraries ship in `backend/.venv`, so they
  follow the installed version (`make setup` creates their targets, `make check` checks them). Never
  edit a linked skill. `.vscode/`: editor settings that match the checks.

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
  Commit subjects, PR titles and final squash subjects follow "Commit style" below.
- **Merge on green.** When the pull request is complete (final description, nothing left to
  decide), mark it with `gh pr merge --squash --auto`: GitHub merges it as soon as the required
  checks `Backend` and `Frontend` pass, and never if they fail. If the CI fails, fix and push; the
  mark stays. If the checks already passed, `--auto` refuses ("clean status"): merge with
  `gh pr merge --squash`. In every case, pass `--subject "$pr_title"` with the final PR title
  as described in `ship-a-change`. This holds only while `main` requires those checks (README, "Deploy"): the
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
  the browser's. Style components with Tailwind utility classes in `className`; `src/index.css` only holds
  the theme and the base look of plain elements. For ready components, shadcn/ui (its CLI) in its own pull request.
- **SQL, no ORM.** Queries are plain SQL run with asyncpg, with `$1` parameters (never string
  formatting: ruff's `S608` rejects it), next to the code that uses them; rows become Pydantic models right there. Write the
  SQL yourself and do not add an ORM or a query builder: explicit SQL is easier to review and test.
- **Migrations.** A schema change is a new file `backend/src/my_project/db/migrations/NNNN_short_name.sql`
  (next number). Never edit an applied migration: the runner stores checksums and refuses changed files.
  The runner is idempotent and takes a PostgreSQL advisory lock, so concurrent starts are safe.
  Each file runs in one transaction: a statement PostgreSQL refuses inside one (`CREATE INDEX
  CONCURRENTLY`) fails; the docstring of `db/migrate.py` says what to do instead.
- **Git worktrees.** Several worktrees can run `make setup`, `make check` and the tests at the same
  time. They share the local PostgreSQL, and each worktree has its own databases in it,
  a development database named by `bash scripts/db-name.sh` and its disposable `-test` database.
  The main checkout keeps `my_project` for development. `make db-up` creates them and writes the worktree's
  `MY_PROJECT_DATABASE_URL` to its `backend/.env`, so `make`, the app and the CLI all use them. `make db-down`
  stops PostgreSQL for every checkout. A removed worktree's databases stay: `docker compose exec
  postgres psql -U my_project -l` lists them and `docker compose exec postgres dropdb -U my_project <name>` drops one.
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
- **The agent.** Agent code lives in `agent/`: instructions and tools in `assistant.py` (more
  agents next to it), the model only from `MY_PROJECT_AI_MODEL` and the provider's own key variable, never
  a key in code. The agent is built without a model, so the API starts without a key and
  `/api/agent` answers 503 until one is set. Every run passes `assistant.LIMITS`. Tests never call
  a real model (`tests/conftest.py` blocks it): use Pydantic AI's `TestModel` or `FunctionModel`,
  as `tests/test_agent.py` does. The route needs a signed-in user (`CurrentUser`).
  The `building-pydantic-ai-agents` skill has the patterns; Logfire is already set up for the
  agent (`instrument_agent` in `observability.py`).
- **Configuration.** New settings go in `settings.py` with a local default and the `MY_PROJECT_` prefix,
  and in `backend/.env.example`. Secrets never enter the repository; everything runs locally without credentials.
- **Library skills are generic; this file wins.** Where a linked library skill and this file or
  the project's own skills disagree, follow this project. Known differences: the `fastapi` skill
  runs the app with `fastapi dev` (here `make dev`) and suggests FastAPI's native OpenTelemetry,
  but Logfire traces the requests here (`observability.py`);
  it suggests SQLModel, but queries here are plain SQL with asyncpg ("SQL, no ORM");
  it presents FastAPI Cloud as the way to deploy, but this project deploys to Render ("Deploy");
  it recommends ty, but the type checker here is pyright;
  `logfire-instrumentation` suggests `logfire run` and its own `configure()`, but Logfire is
  configured once in `observability.py` (add `instrument_*()` calls there). Skip its first and last
  steps, signing in (`whoami`, `auth`, `projects`) and checking that data reached Logfire: work on
  the code without signing in, verify with pytest (tests never send) and, after a deploy, with
  `obs status`. Logfire accounts, projects and tokens are for the user.
  `building-pydantic-ai-agents`, `logfire-evals` and `logfire-gateway` start with a model in
  `Agent(...)`, `logfire.configure()` next to the agent and Logfire or Gateway sign-in
  (`logfire-cli auth`, `whoami`, keys), and say not to use `send_to_logfire='if-token-present'`:
  here the agent has no model of its own (`MY_PROJECT_AI_MODEL`), Logfire is configured once in
  `observability.py` with `if-token-present` on purpose (nothing is sent without a token), and
  keys are for the user.
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
  Dependabot's updates within a range only change the lockfiles. Raise a range in
  `backend/pyproject.toml` or `frontend/package.json` only when the code needs the newer version:
  the template owns those lines, and `copier update` conflicts where both sides changed one.

## Commit style

This project's saved Copier answer is `commit_style=gitmoji`. Apply it to every new
agent-authored commit subject, PR title and final squash subject. Use one concise English
imperative sentence describing the result, without a trailing period; explain why in the body.

Format: `<emoji> <summary>`, with exactly one Unicode emoji and one space (no `:shortcodes:`).
Use this small Gitmoji-based vocabulary; choose the main purpose of a mixed change, not every
file it touches. A feature's tests and docs keep the feature category; separate test-only or
docs-only changes use their own category.

| Emoji | Purpose | Example |
| --- | --- | --- |
| ✨ | Feature, including the initial project | `✨ Add account export` |
| 🐛 | Bug fix | `🐛 Reject expired sessions` |
| 📝 | Documentation only | `📝 Explain local setup` |
| ♻️ | Refactoring without behavior changes | `♻️ Extract session lookup` |
| ✅ | Tests only | `✅ Cover expired sessions` |
| 👷 | CI and build workflows | `👷 Run browser tests in CI` |
| ⬆️ | Dependency upgrades | `⬆️ Upgrade FastAPI` |
| 🔧 | Configuration and other maintenance | `🔧 Configure the test database` |

The summary must make sense without the emoji: it is a visual cue, not the only explanation.

For the PR and squash, summarize the whole change; individual commits describe their own result.
Before merging, normalize the final PR title (including bot PRs), explicitly use it as the squash
subject, and verify the resulting commit on `main`. Do not rewrite existing commits to change
their style. Describe breaking changes and migration steps in words in the body and release notes.
This is not Conventional Commits and does not automate versions or changelogs; tools expecting
`feat:` / `fix:` need a separate project decision and configuration. No commit hook is required.

To change the saved choice, use `copier update --defaults --data commit_style=plain` (without
emojis) or `--data commit_style=gitmoji`. Commit `.copier-answers.yml` and the rendered instructions;
future updates keep that answer. Projects without this answer take `gitmoji` on their first update;
pass `--data commit_style=plain` on that update to retain the previous plain style.

## Deploy

The API runs on Render (Docker, Frankfurt, free plan) from `render.yaml`. Migrations run when it
starts (`MY_PROJECT_MIGRATE_ON_START`, on by default here): the free plan has no pre-deploy step. Production PostgreSQL is Neon (EU region). Logfire receives the traces when `LOGFIRE_TOKEN` is set. The agent needs its provider's key on the platform (`ANTHROPIC_API_KEY` for the default model). The first administrator is created with the CLI against the production database (README, "Accounts").
The one-time manual steps (accounts, secrets, variables) are in the README, "Deploy". Never create
or change cloud services without the user's explicit go-ahead.

## Template updates

The project can take later improvements of its template: with a clean worktree, run
`copier update --defaults` (add `--vcs-ref=HEAD` for the template's latest commit), resolve any
conflict markers, run `make setup` and `make check`, and open a pull request with the result.
Read the template's release notes first, from the project's version (`_commit` in
`.copier-answers.yml`) to the latest; the template's repository is `_src_path` there. They name any
new default the project would take and the `--data` that keeps the old behavior: tell the user
before taking one.
