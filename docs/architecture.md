# Architecture

How Nexus is put together and why. The order of work is in [build-plan.md](build-plan.md); each decision
below links to its record in [adr/](adr/).

## The shape of the system

```
┌──────────────────────── Next.js web app ────────────────────────┐
│ Agent Studio (canvas) │ Test run │ Approvals │ Knowledge graph  │
│ Published apps (chat, reports) for business users               │
└───────────────────────────────┬─────────────────────────────────┘
                                │ /api (same origin, proxied)
┌───────────────────────── FastAPI ───────────────────────────────┐
│ Auth & workspaces │ Agents & versions │ Runs │ Approvals │ Graph │
└───────┬──────────────────────┬───────────────────────┬──────────┘
        │                      │                       │
┌───────▼───────┐  ┌───────────▼──────────┐  ┌─────────▼─────────┐
│ Collector     │  │ Agent runtime        │  │ Postgres          │
│ Snowflake,    │  │ plan → validate →    │  │ + Apache AGE      │
│ Databricks,   │  │ approve → execute →  │  │ knowledge graph,  │
│ dbt, lineage  │  │ verify               │  │ context graph,    │
└───────────────┘  └───────────┬──────────┘  │ runs, audit       │
                               │             └───────────────────┘
                   ┌───────────▼───────────┐
                   │ Snowflake │ Databricks│  (the user's own permissions)
                   │ DuckDB (combine)      │
                   └───────────────────────┘
```

Three processes: the **API** (FastAPI), the **worker** (runs, collection jobs) and the **web app**
(Next.js). One database: **Postgres**, which also hosts the knowledge graph through the Apache AGE extension.

## Stack

| Layer | Choice | Record |
|---|---|---|
| Backend API and worker | Python 3.12, FastAPI, SQLAlchemy Core, Alembic, uv | [ADR-001](adr/ADR-001-python-fastapi-backend.md) |
| System of record | Postgres, with tenants isolated by row-level security | [ADR-002](adr/ADR-002-postgres-and-row-level-security.md) |
| Knowledge graph | Reviewed record in Postgres, approved graph in Apache AGE | [ADR-003](adr/ADR-003-knowledge-graph-in-apache-age.md), [ADR-011](adr/ADR-011-graph-record-and-projection.md) |
| Context graph | Append-only Postgres tables linked to graph nodes | [ADR-004](adr/ADR-004-context-graph-append-only.md) |
| Agent definition | One versioned agent spec, JSON Schema as the source of truth | [ADR-005](adr/ADR-005-visual-builder-first-one-agent-spec.md) |
| Agent runtime | Our own, on the durable run and job queue | [ADR-006](adr/ADR-006-own-agent-runtime.md) |
| Human-in-the-loop | Durable run states, not pop-ups | [ADR-007](adr/ADR-007-human-in-the-loop-as-run-states.md) |
| Guardrails | Checked in code: read-only SQL (sqlglot), user's permissions, number verification | [ADR-008](adr/ADR-008-guardrails-in-code.md) |
| Combining across warehouses | DuckDB inside the worker, on bounded results | [ADR-009](adr/ADR-009-combine-across-warehouses-in-duckdb.md) |
| Industry focus | Industry packs loaded as data, later | [ADR-010](adr/ADR-010-industry-packs-as-data.md) |
| Frontend | Next.js, React Flow for the canvas | [ADR-001](adr/ADR-001-python-fastapi-backend.md), [ADR-005](adr/ADR-005-visual-builder-first-one-agent-spec.md) |

## Building blocks

### Workspaces, people and roles (M0)

A **workspace** is one customer. Every tenant table carries `workspace_id`, and Postgres row-level security
limits each transaction to the workspace set in `app.workspace_id`. The API and worker connect as
`nexus_app`, which does not own the tables and is subject to the policies. Migrations run as `nexus_owner`.

Roles are permissions, not a ladder, because the people who approve are not the people who build:

| Role | Can |
|---|---|
| **admin** | Everything, including people, AI models and connections |
| **steward** | Approve knowledge-graph changes; approve runs |
| **developer** | Build, test and publish agents; approve runs |
| **analyst** | Run agents and approve their own plans |
| **viewer** | Use published apps |

### AI models (M0)

Bring your own: Claude, GPT, Gemini, and any OpenAI-compatible endpoint (Azure OpenAI, OpenRouter, Ollama,
vLLM). Keys are encrypted with AES-256-GCM under a platform key, with the workspace id bound in, so a key
copied into another workspace's row does not decrypt. One adapter interface hides the providers from the
runtime.

### Durable runs (M0)

A **run** is one execution of an agent. Runs are executed by workers that claim jobs from a Postgres queue
(`FOR UPDATE SKIP LOCKED`), so any number of workers can run side by side.

```
queued ──► running ──► succeeded
              │  ▲
              ▼  │ (a person answers)
           waiting
              │
   failed ◄───┴───► cancelled
```

- Every step is written as it happens: a plain-language line for people and structured detail for engineers.
- Tokens and cost are metered per run, with step, token and spending limits.
- A run can be stopped at any time.
- A worker that dies is detected; its run is marked interrupted, never silently repeated (paid AI work).
- `waiting` is how human-in-the-loop works: the run's state is saved, the job ends, and a new job resumes the
  run when a person answers. Nothing is held in memory while a person decides.

### Connections and the knowledge graph (M1)

A **connection** is one warehouse (Snowflake, Databricks, or Postgres). Its secret settings are encrypted
like AI keys and never returned. Nexus reads it with read-only queries: tables, columns, comments and
declared foreign keys.

The **knowledge graph** is what is true about the business: tables, columns, joins, entities and metrics.
Everything read from a warehouse or suggested by Nexus arrives as a **proposal**; only **approved** items reach
agents. Approving a table approves its columns; a join, metric or entity needs its tables approved first.
Retiring a table retires everything that depends on it.

**Join suggestions** use three kinds of evidence: declared foreign keys; names (`customer_ref` and a table
`customers` with an `id`); and data (a sample of the referencing column's values is looked up in the other
column, which must also be a key). Name matches are proposed only when the data agrees, so joins across
warehouses come with evidence. A rejected suggestion is never proposed again.

**Metrics** are an aggregate over one table, with an optional filter, in that warehouse's SQL. They are
checked by parsing (sqlglot): one aggregate expression, no subqueries, only the table's columns.

Each approved change is a new **graph version**. The record lives in tables (`kg_items`, `kg_versions`) and the
approved graph is projected into Apache AGE for traversal, one graph per workspace, reachable only through a
database function scoped to the transaction's workspace
([ADR-011](adr/ADR-011-graph-record-and-projection.md)). Join paths can be found as of any version.

### Context graph (M3)

What happened and why: questions, plans, queries, approvals, corrections and exceptions, each linked to the
knowledge-graph nodes it touched. It is append-only. Corrections that recur become proposals to change the
knowledge graph.

### Agent Studio (M2, M4)

The canvas edits a versioned **agent spec**. The runtime executes the spec; the SDK, later, writes the same
spec. Node groups: Start, Knowledge, Data, Reasoning, Flow (including Sub-agent for multi-agent work), Human
(Approval, Ask for clarification, Review before publishing) and Output. **Verify numbers** is always on.

### Agent runtime (M2, M3)

`plan → validate → approve → execute → verify`. Validation is code, not a prompt: every table, column, join and
metric must exist in the approved graph; the SQL must be read-only; the user must have permission; cost and
row limits must hold. Every number in a result must trace to a cell of a query result.

## Things no canvas can turn off

Read-only SQL; the user's own warehouse permissions; cost and row limits; number verification; approvals
that policy requires; workspace isolation; the audit trail.

## Repository layout

```
apps/web/            Next.js web app
services/api/        FastAPI API, worker, migrations and tests
  src/nexus/
    ai/              model adapters, registry, encrypted keys
    api/             HTTP routes
    connectors/      Snowflake, Databricks and Postgres: read-only metadata and samples
    graph/           knowledge graph: collection, join suggestion, metrics, review, AGE projection
    runtime/         durable runs (and, from M2, the agent runtime)
infra/               local Postgres (with Apache AGE)
docs/                build plan, architecture, decision records
scripts/             developer scripts
```
