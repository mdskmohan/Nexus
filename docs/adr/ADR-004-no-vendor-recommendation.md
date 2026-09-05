# ADR-004: No cross-vendor recommendation

- **Status:** Accepted
- **Date:** 2026-09-05

## Context

An earlier version of the strategy included recommending which platform a workload should
run on — comparing Snowflake credits against Databricks DBUs against BigQuery slots and
advising the customer accordingly. It is a genuinely differentiated feature, and one the
platform vendors structurally cannot copy.

It is also incompatible with a partnership-led go-to-market. We need deep integration
access to Snowflake and Databricks and we intend them to be our first channel. Being
positioned as the layer that advises customers to leave them makes us an adversary of the
organisations whose co-selling motion we depend on.

## Decision

Nexus does not recommend which vendor to use. The customer chooses the platform; Nexus
compiles onto it and operates it well.

Design intelligence is retained but redirected: **how to build this well on the platform
you already chose.** Incremental versus full refresh, partition and clustering strategy,
warehouse sizing, test coverage, orchestration granularity. None of that threatens a
platform vendor — it makes their platform perform better, which aligns our product with
their consumption incentives.

Nexus remains vendor-neutral in *execution* — we integrate with everything — without being
vendor-neutral in *advice*.

## Consequences

**Good.** Partnership-safe. The pitch to a platform vendor becomes consumption
acceleration plus retention, which is what their partner programmes are built to fund.

**Costly.** We give up the sharpest available answer to "why won't Databricks build this."
The remaining answer — that a real use case spans ingestion, warehouse, transformation,
orchestration and BI, and no single vendor owns that chain — is good but less pointed.

**Reversible.** This is a sequencing decision, not a permanent one. Cross-vendor cost
comparison can return once we have enough leverage that partners need us more than we
need them. It should not return before then.

## Alternatives considered

- **Ship recommendation anyway.** Stronger product, no partnerships. Rejected given the
  partnership-led GTM in [ADR-002](ADR-002-creation-first-wedge.md).
- **Recommend privately, stay quiet publicly.** Rejected. It leaks, and it would poison
  the partner relationship precisely when we are most dependent on it.
