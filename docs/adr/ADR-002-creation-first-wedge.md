# ADR-002: Lead with creation, not diagnosis

- **Status:** Accepted
- **Date:** 2026-09-05

## Context

Two possible wedges into the market:

- **Diagnosis-first** — connect read-only, explain why pipelines broke, then earn the
  right to fix them.
- **Creation-first** — take a use case, design and deploy the pipeline, then operate it.

On customer-trust grounds diagnosis is the easier sale. It needs only read access, the
pain already has a budget line, and "explain this failure" is a far smaller ask than
"write my production pipeline."

However, the go-to-market strategy is partnership-led: Snowflake and Databricks are the
intended first channel.

## Decision

Lead with creation, framed as **"we build your new pipelines, and we keep them running."**

The deciding factor is partnership alignment. Diagnosis is a weak pitch to a platform
vendor — helping customers understand failures does nothing for consumption. Creation is
a consumption accelerator and a time-to-value story their field teams can co-sell, which
is the thing partner organisations exist to fund.

Creation also hands us diagnosis on easy mode: for a pipeline we designed, we hold the
intent, the contract and the expected shape, so root-causing a failure does not require
solving the lift problem first.

## Consequences

**Good.** A single coherent V1 that includes operation without depending on the hardest
technical bet. Greenfield pipelines are a safe proving ground for autonomous repair
because we own them and the blast radius is known.

**Costly.** Creation is a harder enterprise sale than diagnosis, and it competes more
directly with what the platform vendors are building inside their own ecosystems. Our
answer is span: a real use case crosses ingestion, warehouse, transformation,
orchestration and BI, and no single platform owns that whole chain.

**Deferred.** Lifting existing pipelines moves to act two, once trust is established.
[ADR-001](ADR-001-pipeline-spec-as-core-abstraction.md) ensures nothing built now is
thrown away when we get there.

## Alternatives considered

- **Diagnosis-first.** Better standalone business, materially worse partnership pitch.
  Revisit if the partnership channel does not materialise.
- **Both at once.** Rejected. Three products at V1 means none of them work.
