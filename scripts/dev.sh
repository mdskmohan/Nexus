#!/usr/bin/env bash
# Start the whole product for local development: database, migrations,
# API (:8100), background worker, and web app (:3100). Ctrl-C stops everything.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

docker compose -f infra/docker-compose.yml up -d --wait postgres
(cd services/api && uv run alembic upgrade head)

pids=()
cleanup() { kill "${pids[@]}" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

(cd services/api && exec uv run uvicorn nexus.main:app --port 8100 --reload --reload-dir src) &
pids+=($!)
# The worker restarts on code changes too (watchfiles ships with uvicorn[standard]).
(cd services/api && exec uv run watchfiles --filter python nexus-worker src) &
pids+=($!)

# Next.js needs Node >= 20.9; use nvm's Node 22 when it is installed.
if [ -s "$HOME/.nvm/nvm.sh" ]; then
  # shellcheck disable=SC1091
  . "$HOME/.nvm/nvm.sh" >/dev/null
  nvm use 22 >/dev/null 2>&1 || true
fi
cd apps/web
[ -d node_modules ] || npm install
NEXT_TELEMETRY_DISABLED=1 exec npx next dev --port 3100
