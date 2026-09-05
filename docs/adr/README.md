# Architecture decision records

One file per decision. An ADR records *why* a choice was made and what it cost, so a
future reader can tell a deliberate trade-off from an accident.

| # | Decision | Status | Summary |
| --- | --- | --- | --- |
| [001](ADR-001-pipeline-spec-as-core-abstraction.md) | PipelineSpec as the core abstraction | Accepted | One vendor-neutral IR serves create, adopt and operate, instead of three data models |
| [002](ADR-002-creation-first-wedge.md) | Lead with creation, not diagnosis | Accepted | Diagnosis is the easier sale; creation is the far better partnership pitch, and partnerships are the channel |
| [003](ADR-003-autonomy-levels.md) | Autonomy levels and the execution boundary | Accepted | The model proposes, a deterministic policy engine decides. No path to a customer system skips the gate |
| [004](ADR-004-no-vendor-recommendation.md) | No cross-vendor recommendation | Accepted | Advising customers which platform to use makes adversaries of the partners we depend on |
| [005](ADR-005-integration-priorities.md) | Integration priorities | Accepted | Five P0 integrations close the V1 loop; tiers for everything else with the reasoning |

## Open questions

Tracked here so they are not lost between ADRs.

- **Partial lifted specs.** `PipelineSpec` requires `owner`, `target` and `schedule`;
  a dbt manifest supplies none of them, so a dbt-only lift cannot produce a valid spec.
  To be decided with Airflow data in hand, then recorded as an amendment to ADR-001.
- **Streaming and the IR.** The IR assumes batch. Kafka and Flink need a different
  execution model (ADR-005 defers them on exactly this ground). Whether that is IR v2
  or a separate spec type is undecided.

## Writing one

Use the existing files as the template. The structure is Context → Decision →
Consequences → Alternatives considered.

Two rules worth stating: **consequences must include the costs**, not only the
benefits — an ADR listing no downside has not finished thinking. And **alternatives
must be real ones** that were genuinely weighed, with the reason each lost.

Raise an ADR whenever a change alters the IR, crosses a subsystem boundary, commits us
to a vendor, or would be expensive to reverse.
