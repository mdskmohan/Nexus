# Nexus

**The AI control plane for enterprise data engineering.**

A customer describes what they need. Nexus designs the pipeline end to end, compiles it
onto their existing stack, deploys it, and then operates it — monitoring, diagnosing
failures, and proposing verified repairs.

Nexus does not replace Snowflake, Databricks, dbt, Airflow or Fivetran. It operates them.

---

## The one-line pitch

> Describe the data product you need. We design it, build it on your stack, and keep it running.

## What Nexus is not

- Not another orchestrator, warehouse, or dbt alternative
- Not another observability dashboard
- Not a vendor-recommendation engine — Nexus compiles onto the platform you already chose
  (see [ADR-004](docs/adr/ADR-004-no-vendor-recommendation.md))
- Not an LLM wrapper. The model reasons; the control plane decides what it may touch.

---

## Architecture in one picture

```
   Use case (natural language + structured intake)
        │
        ▼  design
   ┌─────────────────┐
   │  PipelineSpec   │  vendor-neutral IR — the durable artifact
   └─────────────────┘
        │
        ├──► compile ──► dbt project + Airflow DAG + warehouse DDL
        │
        ▼  deploy
   Running pipeline on the customer's stack
        │
        ▼  observe
   ┌─────────────────┐
   │ Environment     │  entities, lineage, ownership, runtime history
   │ Graph           │
   └─────────────────┘
        │
        ▼  on failure
   Evidence collectors ──► ranked hypotheses ──► root cause
        │
        ▼
   Remediation (PR) ──► sandbox validation ──► policy gate ──► deploy ──► verify
```

The `PipelineSpec` is the centre of the system. Creation compiles *out* of it; adopting an
existing pipeline lifts *into* it. Both directions serve the same diagnosis engine.
See [ADR-001](docs/adr/ADR-001-pipeline-spec-as-core-abstraction.md).

---

## Repository layout

```
apps/web/          Next.js 14 App Router frontend
services/api/      FastAPI backend
  nexus/ir/          PipelineSpec — the vendor-neutral IR
  nexus/compiler/    IR -> vendor artifacts (dbt, Airflow, DDL)
  nexus/graph/       Environment graph: entities, edges, traversal
  nexus/diagnosis/   Evidence collectors and hypothesis ranking
  nexus/policy/      Autonomy levels and action gating
docs/              Architecture and ADRs
```

## Getting started

Requirements: Python 3.11+, **Node 20+** (Next.js 14 refuses to build on Node < 18.17;
`.nvmrc` pins 22, so `nvm use` in `apps/web` picks the right one).

```bash
make setup     # install backend and frontend dependencies
make dev       # run API on :8000 and web on :3000
make test      # run the full test suite
make check     # lint, format check, and type check
```

## Documentation

| Document | Purpose |
| --- | --- |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | How the system fits together and why |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Coding standards and review expectations |
| [docs/adr/](docs/adr/) | Architecture decision records |

## Status

Pre-alpha. The IR and compiler are under active development; nothing here has been run
against a production customer environment.
