# Public demo operations

This repository owns the demo-specific changes. The template contains no demo domains or credentials.

| Component | Resource | Configuration |
| --- | --- | --- |
| Visor | Vercel `full-stack-blueprint-example` | GitHub `main`, root `frontend`, public production domain |
| API | Render `full-stack-blueprint-example-api` | Free, Frankfurt, Docker, `/api/healthz`, deploy after CI passes |
| Database | Neon `full-stack-blueprint-example` (`bold-salad-93466923`) | Free, PostgreSQL 18, Frankfurt, dedicated `blueprint_example` database |
| Traces | Logfire `ebotiab/full-stack-blueprint-example` | US region; server write token required, read token for verification |

Render's Blueprint automatically syncs `render.yaml` from `main`. `DATABASE_URL`, `LOGFIRE_TOKEN`
and `MY_PROJECT_ORIGIN_SECRET` belong only in the service's secret environment. Vercel's
`ORIGIN_SECRET` must match the API value. Only `VITE_PUBLIC_DEMO=true` enables the visitor button;
never put privileged credentials in a `VITE_` variable. Browser Logfire, when configured, uses
only a restricted frontend application token with the production origin allowed.

The public account is created idempotently at API startup with `MY_PROJECT_DEMO_ENABLED=true`.
It is not an administrator. The public deployment refuses mutations other than signing in and
ending the caller's own session. No model key is provisioned, and the agent is not offered.
Login attempts share the PostgreSQL token bucket (burst of ten, one replenished per minute).
Do not store private data in this database or reuse this mode for another application.

## Verify a release

After merging on green, wait for both providers' deployments, then compare their Git SHAs with
the intended commit. A frontend-only change can leave Render on the last backend commit because
its root directory is `backend`.

```bash
node scripts/verify-live-demo.mjs
cd backend
uv run my-project obs status --commit <API-commit> --wait 15
```

The browser script starts without saved authentication, follows the README link, signs in,
reads real API data, reloads to verify session and data persistence, checks isolation from an
anonymous browser, signs out, opens Swagger, and fails on browser/server errors. Optionally set
`EXPECTED_API_COMMIT` and `DEMO_SCREENSHOT` (a local image path). It never mocks requests or uses
a Vercel protection bypass. Keep browser state and traces containing cookies out of artifacts.

## Template updates

The real API address is a Copier answer (`api_public_url`), updated with Copier rather than by
editing `.copier-answers.yml`. Demo-only modules, migration, documentation and browser verification
script are local additions. Copier's three-way merge preserves changes in shared files.

Before merging a template update, run the template's `scripts/update-example.sh` on a clean,
isolated clone of this repository, then `make setup && make check`. Verify that the README's two
public links, both documentation proxy rules, visitor restrictions and `render.yaml` service name
remain present. Resolve any future conflicts explicitly; never overwrite with a fresh template copy.
The update to template HEAD `d9bddc8` was tested with all fourteen checks passing.
