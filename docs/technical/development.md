# Development and setup

## Requirements

- Docker (for Postgres)
- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Node.js 20.9+ (22 recommended)
- For the AI features: a key for Claude, GPT or Gemini (or another OpenAI-compatible service), or a local model

## First run

```bash
cp .env.example .env
```

Edit `.env`: set `NEXUS_JWT_SECRET` (`openssl rand -hex 32`) and `NEXUS_SECRET_KEY`
(`openssl rand -base64 32`, which encrypts firms' AI keys). `ANTHROPIC_API_KEY` is
optional: firms connect their own AI models in *Firm settings → AI models*; the
platform key is used only by firms that have not.

```bash
make dev
```

`make dev` starts Postgres (port 5544), applies migrations, and runs the API
(:8100), the worker and the web app (:3100). Open http://localhost:3100 and
create a firm, or load the demo firm:

```bash
cd services/api && uv run nexus-seed-demo
```

The demo firm has a matter with a sample NDA (with deliberate issues for the
reviewer to catch) and an email containing a planted AI instruction (to show
the upload scan), and an Indian matter with a Pune services agreement. The
sign-in details are printed by the command. Connect an AI model in *Firm
settings → AI models* to use the AI features (for local testing, Ollama with a
model that supports tool calling, and a context window of at least 16,000
tokens for reviews and drafts).

## Tests

```bash
make test
```

Tests run against a real Postgres: a `nexus_test` database on the dev server,
created and migrated from scratch each session. They cover row-level security,
the append-only audit trail, roles, ingestion of every supported format,
citation verification, document scans, Word tracked changes, and Word/Excel
rendering. Most tests do not call an AI model. Two live checks run when possible: a real
provider rejecting an invalid key (skipped without network), and a tool-call
round trip on a local Ollama model (skipped unless Ollama has `qwen3:4b`).

## Configuration

All settings are environment variables with the `NEXUS_` prefix (see
`services/api/src/nexus/config.py`):

| Variable | Default | |
|---|---|---|
| `NEXUS_SECRET_KEY` | — | Required to store firms' AI keys (32 bytes, base64) |
| `ANTHROPIC_API_KEY` | — | Optional platform model for firms without their own |
| `NEXUS_MODEL` | `claude-opus-5` | The platform model (with `ANTHROPIC_API_KEY`) |
| `NEXUS_EFFORT` | `high` | `low` / `medium` / `high` / `xhigh` / `max` |
| `NEXUS_MODEL_FALLBACKS` | `true` | Server-side refusal fallbacks |
| `NEXUS_AGENT_MAX_STEPS` | `30` | Default step limit (review 60, draft 80) |
| `NEXUS_AGENT_BUDGET_USD` | `5.00` | Spending limit per task (priced models) |
| `NEXUS_AGENT_TOKEN_BUDGET` | `4000000` | Size limit per task (every model) |
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
