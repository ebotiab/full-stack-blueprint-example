---
name: change-the-api
description: Add or change an API route in My Project end to end — migration, route, pytest test, regenerated OpenAPI schema, typed client in the visor and a Playwright test. Use it for any task that changes what the API returns or accepts.
---

# Change the API

The contract between the API and its clients is `backend/openapi.json`, generated from the code.
Work outward from the database to the visor, so each layer is typed by the one before it.

1. **Schema.** If the data changes, add `backend/src/my_project/db/migrations/NNNN_short_name.sql`
   (next number; plain SQL; one concern per file) and run `make migrate`. Never edit an applied migration.
2. **Route.** In `backend/src/my_project/api/routes.py` (or a new module included in `api/main.py`
   under the `/api` prefix): a Pydantic response model, a typed handler, SQL with
   `$1` parameters through the `ConnectionDep` connection (never string formatting).
3. **Test.** A pytest test in `backend/tests/` for the new behaviour, including its error cases. Tests that need
   PostgreSQL use the `db_url`/`db_conn`/`app_settings` fixtures from `tests/conftest.py`.
4. **Contract.** `make types`. Review the diff of `backend/openapi.json`: it is what clients see.
5. **Visor.** Call it with `api.GET('/api/…')` / `api.POST(…)` from `frontend/src/api/client.ts`; the types
   come from `schema.d.ts`, so a wrong path or field fails `make check`. Add or update a Playwright
   test in `frontend/e2e/` that mocks the route with `page.route`.
6. **Check and ship.** `make check`, then follow the `ship-a-change` skill.
