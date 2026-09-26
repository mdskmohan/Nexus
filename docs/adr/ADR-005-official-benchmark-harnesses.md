# ADR-005: Measure with official benchmark data and graders

**Status:** Accepted · 2026-09-26

## Context
Claims about legal AI quality are only credible if others can reproduce them.

## Decision
- LegalBench: use the official data, instructions, answer spaces and scoring
  methods from the release; report balanced accuracy for classification tasks.
- Harvey LAB: run the full Nexus pipeline and write deliverables into LAB's
  results layout so LAB's own, unmodified evaluator grades them.
- Publish every result with its command, date, model, effort, sample and cost.

## Consequences
- Results are comparable with other published numbers when run on the same
  judges and samples.
- Full runs are expensive; sampled runs are labelled as samples.
