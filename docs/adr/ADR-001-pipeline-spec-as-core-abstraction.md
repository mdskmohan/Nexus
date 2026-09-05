# ADR-001: PipelineSpec as the core abstraction

- **Status:** Accepted
- **Date:** 2026-09-05

## Context

Nexus has three ambitions that look like three separate products:

1. **Create** — turn a customer's use case into a working pipeline
2. **Integrate** — work with pipelines the customer already has, which we did not build
3. **Operate** — diagnose failures and propose repairs across both

Built naively these are three codebases with three data models, and the company dies of
scope. The design question is whether a single abstraction can serve all three.

## Decision

Introduce a vendor-neutral intermediate representation, `PipelineSpec`, and make it the
centre of the system. Every subsystem reads or writes it; nothing bypasses it.

```
use case  ──design──►  PipelineSpec  ──compile──►  dbt + Airflow + DDL
                            ▲
existing pipeline ──lift────┘
```

- **Creation** is compilation: `PipelineSpec` → vendor artifacts.
- **Integration** is lifting: parse a customer's dbt manifest, Airflow DAGs and warehouse
  lineage, and reconstruct as much of a `PipelineSpec` as the evidence supports.
- **Operation** consumes `PipelineSpec` in both cases, so the diagnosis engine does not
  care which direction a pipeline arrived from.

A lifted spec is explicitly *partial*. Every field carries provenance, and fields we could
not recover are absent rather than guessed. Diagnosis quality degrades gracefully with
how much of the spec we managed to recover.

## Consequences

**Good.** One data model instead of three. The compiler and the lifter are inverse
operations over the same target, so work on either improves both. Adding a vendor is a
new compile target and a new lift parser, not a new product.

**Costly.** The IR must be expressive enough for real pipelines but neutral enough to
compile to genuinely different execution models — dbt's declarative SQL and Spark's
imperative DataFrames do not have the same shape. We will get this wrong and have to
version it, so the IR is versioned from commit one.

**Risk.** The lift direction is the hard technical bet of the company. If we cannot
recover enough intent from a stranger's production estate, the integration story fails
and Nexus is only useful on pipelines it created. This should be tested against a real
messy estate before we build much on top of it.

## Alternatives considered

- **Separate models per capability.** Faster to first demo, but the diagnosis engine would
  need writing twice and the two halves would drift.
- **Adopt dbt's manifest as the IR.** Tempting — it is already the de facto standard and
  we parse it anyway. Rejected because it cannot express ingestion, orchestration, or
  non-dbt transformation, and it ties the company's core abstraction to one vendor's
  release cycle.
