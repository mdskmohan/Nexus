# Development and setup

## Requirements

- Docker (for Postgres)
- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Node.js 20.9+ (22 recommended)
- An Anthropic API key, for the AI features

## First run

```bash
cp .env.example .env
```

Edit `.env`: set `ANTHROPIC_API_KEY`, and set `NEXUS_JWT_SECRET` to the output of `openssl rand -hex 32`.

```bash
make dev
```

`make dev` starts Postgres (port 5544), applies migrations, and runs the API
(:8100), the worker and the web app (:3100). Open http://localhost:3100 and
create a firm, or load the demo firm:

```bash
cd services/api && uv run nexus-seed-demo
```

The demo firm has one matter with a sample NDA (with deliberate issues for the
reviewer to catch) and an email containing a planted AI instruction (to show
the upload scan). The sign-in details are printed by the command.

## Tests

```bash
make test
```

Tests run against a real Postgres: a `nexus_test` database on the dev server,
created and migrated from scratch each session. They cover row-level security,
the append-only audit trail, roles, ingestion of every supported format,
citation verification, document scans, Word tracked changes, and Word/Excel
rendering. They do not call the AI model.

## Configuration

All settings are environment variables with the `NEXUS_` prefix (see
`services/api/src/nexus/config.py`):

| Variable | Default | |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Required for AI features |
| `NEXUS_MODEL` | `claude-opus-5` | Model for all agents |
| `NEXUS_EFFORT` | `high` | `low` / `medium` / `high` / `xhigh` / `max` |
| `NEXUS_MODEL_FALLBACKS` | `true` | Server-side refusal fallbacks |
| `NEXUS_AGENT_MAX_STEPS` | `30` | Default step limit (review 60, draft 80) |
| `NEXUS_AGENT_BUDGET_USD` | `5.00` | Spending limit per task |
| `NEXUS_MAX_UPLOAD_MB` | `50` | |
| `NEXUS_SESSION_HOURS` | `12` | |
| `NEXUS_COOKIE_SECURE` | `false` | `true` behind HTTPS |
| `NEXUS_DATABASE_URL` | app role on :5544 | |
| `NEXUS_DATABASE_OWNER_URL` | owner role on :5544 | Migrations only |
| `NEXUS_STORAGE_DIR` | `var/storage` | |

## Migrations

```bash
cd services/api && uv run alembic revision -m "describe change"
```

Write migrations in SQL (`op.execute`). Any new tenant table needs `firm_id`,
`ENABLE` + `FORCE ROW LEVEL SECURITY`, the `tenant_isolation` policy and a
grant to `nexus_app`; follow `0001_initial.py`.

## Code layout conventions

- SQL is written directly (`db.rows`, `db.row`, `db.scalar`) inside a
  `tenant()` transaction.
- Every user-visible action writes an audit event.
- User-facing text (API errors, step titles, UI) is plain English for lawyers.
  Technical detail goes in logs and `run_steps.detail`.
