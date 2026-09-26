# ADR-004: Postgres full-text search first; embeddings later

**Status:** Accepted · 2026-09-26

## Context
Agents need to find relevant passages in a matter. Legal documents lean on
defined terms and clause names, which keyword search matches exactly, while
semantic search helps when wording differs.

## Decision
Start with Postgres full-text search (English stemming, heading weighted above
body, all-terms-then-any-terms fallback), and have agents search several times
with different wordings and read around hits. Reviews must record a finding
for every playbook point, which forces a deliberate search for "missing" items.

## Consequences
- No extra service, no embedding provider, no second copy of client text.
- Unusually worded clauses can be missed; mitigated by multi-query search and
  reading documents in order (the review agent reads the whole contract).
- Revisit with hybrid search (pgvector) once benchmark results show retrieval
  misses are a meaningful share of errors.
