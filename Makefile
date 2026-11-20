# Tasks for My Project. `make help` lists them.
#
# Every target runs without prompts and ends with a reliable exit code; the multi-step ones
# (setup, check, test) keep going after a failure and finish with a short summary
# (scripts/steps.sh). The CI runs `make check-backend` and `make check-frontend`: the same steps.
SHELL := bash
.SHELLFLAGS := -euo pipefail -c
.DEFAULT_GOAL := help
MAKEFLAGS += --no-print-directory

API_PORT ?= 8000
WEB_PORT ?= 5173
# pytest's throwaway database (emptied by the tests). The CI sets its own.
TEST_DATABASE_URL ?= postgresql://my_project:my_project@localhost:5434/my_project_test
STEPS := bash scripts/steps.sh

BACKEND_STEPS := \
	"Python format (ruff format)::cd backend && uv run ruff format --check ." \
	"Python lint (ruff check)::cd backend && uv run ruff check ." \
	"Python types (pyright)::cd backend && uv run pyright" \
	"OpenAPI schema up to date (backend/openapi.json)::$(MAKE) openapi-check" \
	"Python tests (pytest + PostgreSQL)::cd backend && MY_PROJECT_TEST_DATABASE_URL='$(TEST_DATABASE_URL)' uv run pytest"

FRONTEND_STEPS := \
	"Visor format (oxfmt)::cd frontend && npm run --silent fmt:check" \
	"Visor lint (oxlint)::cd frontend && npm run --silent lint" \
	"Visor types (tsc)::cd frontend && npm run --silent typecheck" \
	"API types up to date (frontend/src/api/schema.d.ts)::$(MAKE) schema-check" \
	"Visor unit tests (Vitest)::cd frontend && npm run --silent test" \
	"Visor build (vite build)::cd frontend && npx vite build" \
	"Visor browser tests (Playwright)::cd frontend && npx playwright test"

.PHONY: help doctor setup dev check check-backend check-frontend e2e schema-check test fmt types openapi-check migrate db-up db-down

help: ## List the tasks
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  make %-15s %s\n", $$1, $$2}'

doctor: ## Check the tools (uv, Node, Docker) and say how to fix what is missing
	@bash scripts/doctor.sh

setup: ## Install dependencies, start PostgreSQL, migrate and generate the API schema and types
	@bash scripts/doctor.sh
	@$(STEPS) \
		"Python dependencies (uv sync)::cd backend && uv sync" \
		"Visor dependencies (npm)::cd frontend && if [ -f package-lock.json ]; then npm ci; else npm install; fi" \
		"Playwright browser (Chromium)::cd frontend && npx playwright install chromium" \
		"PostgreSQL (docker compose)::$(MAKE) db-up" \
		"Migrations::cd backend && uv run my-project migrate" \
		"API schema and types::$(MAKE) types"

dev: ## Run the API (:$(API_PORT)) and the visor (:$(WEB_PORT)) with reload; Ctrl-C stops both
	@$(MAKE) migrate
	@trap 'kill 0' EXIT INT TERM; \
		(cd backend && uv run uvicorn my_project.api.main:app --reload --port $(API_PORT)) & \
		(cd frontend && API_PORT=$(API_PORT) npm run dev -- --port $(WEB_PORT) --strictPort) & \
		wait

check: ## Everything the CI checks: format, lint, types, API contract, tests, build, Playwright
	@$(MAKE) db-up
	@$(STEPS) $(BACKEND_STEPS) $(FRONTEND_STEPS)

check-backend: ## The backend half of `make check`
	@$(if $(CI),true,$(MAKE) db-up)
	@$(STEPS) $(BACKEND_STEPS)

check-frontend: ## The visor half of `make check`
	@$(STEPS) $(FRONTEND_STEPS)

test: ## Run the tests: pytest against PostgreSQL and Vitest (Playwright: make e2e)
	@$(if $(CI),true,$(MAKE) db-up)
	@$(STEPS) \
		"Python tests (pytest)::cd backend && MY_PROJECT_TEST_DATABASE_URL='$(TEST_DATABASE_URL)' uv run pytest" \
		"Visor unit tests (Vitest)::cd frontend && npm run --silent test"

e2e: ## Run the Playwright browser tests (they answer /api themselves)
	@cd frontend && npx playwright test

fmt: ## Format and auto-fix: ruff and oxfmt
	@cd backend && uv run ruff format . && uv run ruff check --fix .
	@cd frontend && npm run --silent fmt

types: ## Regenerate backend/openapi.json and the visor's API types after changing the API
	@cd backend && uv run my-project openapi --output openapi.json
	@cd frontend && npm run --silent types

openapi-check: ## Fail if backend/openapi.json does not match the code
	@cd backend && uv run my-project openapi | diff -u openapi.json - \
		|| { echo "backend/openapi.json is out of date: run 'make types' and commit the result."; exit 1; }

schema-check: ## Fail if frontend/src/api/schema.d.ts does not match backend/openapi.json
	@cd frontend && npm run --silent types:print | diff -u src/api/schema.d.ts - \
		|| { echo "frontend/src/api/schema.d.ts is out of date: run 'make types' and commit the result."; exit 1; }

migrate: ## Apply pending SQL migrations to the local database
	@$(MAKE) db-up
	@cd backend && uv run my-project migrate

db-up: ## Start the local PostgreSQL (docker compose) and create the test database
	@docker compose up -d --wait postgres
	@docker compose exec -T postgres psql -U my_project -d my_project -tAc \
		"SELECT 1 FROM pg_database WHERE datname = 'my_project_test'" | grep -q 1 \
		|| docker compose exec -T postgres createdb -U my_project my_project_test

db-down: ## Stop the local PostgreSQL (the data stays in a Docker volume)
	@docker compose stop postgres
