.PHONY: help up down warehouses migrate dev api worker web test lint build

help:
	@echo "make up       start Postgres"
	@echo "make dev      start everything (database, API, worker, web) — open http://localhost:3100"
	@echo "make test     run the backend test suite against a real Postgres"
	@echo "make warehouses  start real MySQL, SQL Server and Oracle for connector tests"
	@echo "make lint     lint the backend"
	@echo "make build    production build of the web app"

up:
	docker compose -f infra/docker-compose.yml up -d --wait postgres

warehouses:
	docker compose -f infra/docker-compose.yml --profile warehouses up -d --wait mysql sqlserver oracle

down:
	docker compose -f infra/docker-compose.yml down

migrate: up
	cd services/api && uv run alembic upgrade head

dev:
	./scripts/dev.sh

api:
	cd services/api && uv run uvicorn nexus.main:app --port 8100 --reload --reload-dir src

worker:
	cd services/api && uv run nexus-worker

web:
	cd apps/web && npx next dev --port 3100

test: up
	cd services/api && uv run pytest -q

lint:
	cd services/api && uv run ruff check src tests

build:
	cd apps/web && npx next build
