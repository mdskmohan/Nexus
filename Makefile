.PHONY: setup dev test check fmt api web

API := services/api
WEB := apps/web

setup: ## Install backend and frontend dependencies
	cd $(API) && python3 -m venv .venv && ./.venv/bin/pip install -e ".[dev]"
	cd $(WEB) && npm install

api: ## Run the API on :8000
	cd $(API) && ./.venv/bin/uvicorn nexus.main:app --reload --port 8000

stack: ## Start the real local stack (Postgres + Airflow)
	docker compose -f stack/docker-compose.yml up -d

stack-down: ## Stop the local stack
	docker compose -f stack/docker-compose.yml down

web: ## Run the web app on :3000
	cd $(WEB) && npm run dev

test: ## Run the full test suite
	cd $(API) && ./.venv/bin/python -m pytest

check: ## Lint, format check, and type check
	cd $(API) && ./.venv/bin/ruff check nexus tests
	cd $(API) && ./.venv/bin/ruff format --check nexus tests
	cd $(API) && ./.venv/bin/mypy nexus
	cd $(WEB) && npm run lint

fmt: ## Format everything
	cd $(API) && ./.venv/bin/ruff format nexus tests
	cd $(API) && ./.venv/bin/ruff check --fix nexus tests
