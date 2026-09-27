# Architecture

## Overview

```
 Browser ──► Next.js web app (apps/web, :3100)
                 │  /api/* proxied (same origin, cookie session)
                 ▼
            FastAPI (services/api, :8100) ──────────────┐
                 │ enqueue jobs                          │ reads/writes as nexus_app
                 ▼                                       ▼
            Postgres job queue ◄── worker (nexus-worker) ──► Postgres 16 (row-level security)
                                        │                    ▲
                                        │ agent loop         │ passages, runs, steps, audit
                                        ▼                    │
                     the firm's chosen model provider ─────┘ (tools execute in the worker)
                     (Claude, GPT, Gemini, OpenAI-compatible, or on-premises)
                                        │
                                  File storage (originals, generated Word/Excel)
```

| Component | Code | Responsibility |
|---|---|---|
| Web app | `apps/web` | The lawyer-facing product. Client components that call `/api`; no business logic. |
| API | `services/api/src/nexus/api` | Auth, roles, request validation, starting tasks, reading results, audit. |
| Worker | `nexus/tasks.py`, `nexus/jobs.py` | Document ingestion and AI runs, off the request path. |
| Ingestion | `nexus/ingest` | Extract text (PDF, Word, Excel, PowerPoint, email, text) and split it into passages. |
| Search | `nexus/search.py` | Postgres full-text search over one matter's passages. |
| AI providers | `nexus/ai` | One interface over Anthropic, OpenAI, Google and OpenAI-compatible models; encrypted firm keys; model choice. |
| Agents | `nexus/agents` | The agent loop and the agents: ask, review, draft, legal notice. |
| India | `nexus/india`, `nexus/playbooks_india.py` | Section 138 timeline and Indian amount formatting; Indian-law playbooks. |
| Guardrails | `nexus/guardrails`, `agents/base.py`, `agents/cite.py` | Citation verification, document scans, limits. |
| Observability | `nexus/observability.py` | Per-step activity record, token and cost metering, firm metrics. |
| Outputs | `nexus/redline.py`, `nexus/deliverables.py` | Review memo, Word tracked changes, Word/Excel drafts. |
| Benchmarks | `nexus/bench` | LegalBench and Harvey LAB runners. |

## Request and task flow

1. **Upload.** `POST /api/matters/{id}/documents` stores the file, inserts a
   `documents` row (status `queued`) and enqueues `ingest_document`.
2. **Ingest (worker).** Extract pages, then chunk them into passages (roughly
   one clause each, carrying the nearest heading), scan for hidden instructions
   and sensitive numbers, insert passages (Postgres builds the full-text index
   column), and mark the document `ready` with its flags.
3. **Start a task.** `POST /ask`, `/reviews` or `/drafts` inserts a `runs` row
   (status `queued`) and enqueues `run_agent`. AI runs are never retried
   automatically: a retry costs money and may give a different answer.
4. **Run (worker).** The agent loop calls Claude with the agent's tools. Each
   tool call executes in the worker against the database, scoped to the run's
   matter and firm, and is recorded as a plain-language step. The finishing
   tool runs the guardrail checks and can send the work back.
5. **Finish.** Output, guardrail summary, tokens and cost are saved. Generated
   files are written as `artifacts`. Status becomes `needs_review`.
6. **Sign-off.** An associate or above approves or sends back; this is audited.

The web app polls a running task every 1.5 s and renders steps as they arrive.

## Why these choices

See the [ADRs](../adr/). In short:

- **Postgres for everything stateful** (data, search, queue, audit): one system
  to secure, back up and reason about. Row-level security gives tenant
  isolation that does not depend on application code being correct.
- **Our own agent loop over a provider-neutral interface**, rather than a framework, so every
  tool call passes through our guardrails and our activity record, and so the
  loop has exactly the properties a law firm needs (bounded steps and spend, no
  retries of paid work, finishing tools that can reject output).
- **Keyword search first.** Legal text is dense with defined terms and clause
  names that keyword search matches exactly; the agents compensate for
  vocabulary gaps by searching several ways. Embedding search is a planned
  addition, not a dependency.
- **Verification in code, not in the prompt.** The model is asked to quote;
  code decides whether the quote is real.

## Repository layout

```
apps/web/                 Next.js 16 app (TypeScript)
services/api/
  src/nexus/              API, worker, agents, guardrails, ingestion, outputs, benchmarks
  migrations/             Alembic migrations (SQL-first; RLS and triggers live here)
  tests/                  pytest against a real Postgres
infra/                    docker-compose for Postgres; role setup
scripts/dev.sh            one-command local stack
docs/                     user guide, legal framework, technical docs, ADRs
```
