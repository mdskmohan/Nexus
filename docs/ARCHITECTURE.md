# Architecture

How Nexus fits together, and why it is shaped this way. Decisions are recorded as
[ADRs](adr/); this document describes the system they add up to.

**Status legend:** ✅ built · 🚧 in progress · ⬜ planned

---

## The shape of the system

```
        use case (natural language + structured intake)
              │
              ▼  design
      ┌───────────────────┐
      │   PipelineSpec    │ ✅  vendor-neutral IR — the durable artifact
      └───────────────────┘
         ▲            │
    lift │            │ compile
         │            ▼
   existing        dbt project + Airflow DAG + warehouse DDL  ⬜
   pipelines                    │
      🚧                        ▼  deploy
                        running on the customer's stack
                                │
                                ▼  observe
                      ┌───────────────────┐
                      │ Environment Graph │ ✅ entities · 🚧 population
                      └───────────────────┘
                                │
                                ▼  on failure
                   evidence collectors ──► ranked hypotheses  ⬜
                                │
                                ▼
              remediation ──► sandbox validation ──► policy gate ⬜
                                │
                                ▼
                        deploy ──► verify ──► rollback
```

## Why the IR is the centre

Nexus has three ambitions that look like three products: create pipelines, adopt
pipelines it did not create, and operate both. Built naively that is three data models
and three codebases.

`PipelineSpec` collapses them. Creation compiles out of it. Adoption lifts into it.
Diagnosis reads it without caring which direction it arrived from. The compiler and the
lifter are inverse operations over one target, so work on either improves both, and
adding a vendor is a new compile target plus a new lift parser — not a new product.

See [ADR-001](adr/ADR-001-pipeline-spec-as-core-abstraction.md).

### The open question

A lifted spec is *partial* by construction, and this is not yet resolved. `PipelineSpec`
requires `owner`, `target` and `schedule`. A dbt manifest contains none of them — dbt
does not know when anything runs or who is on call. So a dbt-only lift cannot currently
produce a valid spec.

Three candidate resolutions: make those fields optional carrying provenance; require a
dbt + orchestrator join before a spec exists; or give partial pipelines their own
representation. **This will be decided with Airflow data in hand rather than guessed at**,
and will amend ADR-001 when it is.

## Layers

### Connectors ✅ interface, 🚧 coverage

Read one external system and emit graph entities. Strictly read-only and strictly
deterministic — no model calls, no writes, no hidden retries. Anything that *changes* a
customer system lives in the execution layer behind the policy engine.

Connectors do not join across systems. Node ids are namespaced (`dbt:model.shop.x`), and
recognising that an Airflow task runs a given dbt model is a separate explicit step,
because that inference is where a lifted graph goes quietly wrong.

What each connector could *not* recover travels with the result as warnings rather than
being logged and discarded. When a lifted pipeline eventually produces a bad diagnosis,
the first question is what the lifter failed to see.

Priorities and status: [integrations.md](integrations.md), [ADR-005](adr/ADR-005-integration-priorities.md).

### Environment graph ✅ entities, 🚧 population

Nodes and directed edges over sources, models, tests, DAGs, tasks and consumers. Edge
direction is always *from depends-on to dependent*, so downstream impact is a forward
traversal from the failing node.

Traversal never branches on vendor. A node knows which system reported it; the code
walking the graph does not care.

### Diagnosis ⬜

The design constraint that matters: **the model ranks and narrates, it does not gather
facts.** A hypothesis tree sits behind a set of deterministic evidence collectors —
schema drift from `INFORMATION_SCHEMA` snapshot diffs, recent deployments from git
history over the failing node's lineage, upstream task failure, source freshness stall,
row-count anomaly, warehouse contention. Each produces timestamped, sourced evidence.

That is what makes a claim like *"salesforce.account.id changed from NUMBER to VARCHAR
27 minutes before the failure"* a citation an engineer can verify independently, rather
than a plausible-sounding guess. It is also the honest answer to "why not just point a
model at the logs."

### Policy and execution ⬜

The model emits a proposed action as data. A deterministic policy engine decides whether
it may run. A separate execution layer runs it. There is no code path from model output
to a customer system that skips the gate.

Actions carry an autonomy level (0 observe → 4 autonomous), configured per customer, per
environment, per action class. Level 4 requires an action be reversible or trivially
re-runnable; anything failing that test cannot be assigned level 4 regardless of customer
appetite. Deleting data is never automated.

See [ADR-003](adr/ADR-003-autonomy-levels.md).

### Web ✅

Next.js 14 App Router, server components by default. Token-driven design system with
light and dark parity-locked. Currently renders fixtures shaped to the real API types,
so swapping in live data is a fetch call rather than a rewrite.

The incident screen is built to show the *argument*, not the conclusion: ranked
hypotheses, contradicting evidence displayed alongside supporting, every claim naming its
source system, and the autonomy gate surfaced rather than hidden — because per ADR-003
the gate is a large part of what the customer is buying.

---

## Repository layout

```
apps/web/                  Next.js frontend
services/api/
  nexus/ir/                PipelineSpec — the vendor-neutral IR
  nexus/graph/             Entities and traversal
  nexus/connectors/        One module per external system
  nexus/compiler/          IR -> vendor artifacts
  nexus/diagnosis/         Evidence collectors and ranking
  nexus/policy/            Autonomy levels and action gating
  tests/fixtures/          Real artifacts from real tools, never handwritten
docs/adr/                  Architecture decision records
```

## Principles

1. **The IR is sacred.** Changing `PipelineSpec` is an ADR-level decision.
2. **The model never executes.** It proposes; the control plane decides and acts.
3. **Evidence over assertion.** No diagnosis without a timestamped, sourced fact
   behind it. "Unknown" beats a confident guess.
4. **Deterministic where possible.** Models for ranking, explanation and language.
   Ordinary code for collecting facts, walking graphs and generating artifacts.
