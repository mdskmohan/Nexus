# Decision records

Each record states one decision, why it was made, and what it costs. Records are not edited after they are
accepted; a later record supersedes an earlier one.

| Record | Decision |
|---|---|
| [ADR-001](ADR-001-python-fastapi-backend.md) | Python and FastAPI for the backend; Next.js for the web app |
| [ADR-002](ADR-002-postgres-and-row-level-security.md) | Postgres as the system of record; tenants isolated by row-level security |
| [ADR-003](ADR-003-knowledge-graph-in-apache-age.md) | Knowledge graph in Apache AGE, behind one graph interface |
| [ADR-004](ADR-004-context-graph-append-only.md) | Context graph as append-only Postgres tables |
| [ADR-005](ADR-005-visual-builder-first-one-agent-spec.md) | Visual builder first; one versioned agent spec for canvas, runtime and SDK |
| [ADR-006](ADR-006-own-agent-runtime.md) | Our own agent runtime; no external agent frameworks |
| [ADR-007](ADR-007-human-in-the-loop-as-run-states.md) | Human-in-the-loop as durable run states |
| [ADR-008](ADR-008-guardrails-in-code.md) | Guardrails enforced in code |
| [ADR-009](ADR-009-combine-across-warehouses-in-duckdb.md) | Combine results across warehouses in DuckDB |
| [ADR-010](ADR-010-industry-packs-as-data.md) | Industry packs loaded as data, built later |
| [ADR-011](ADR-011-graph-record-and-projection.md) | The knowledge graph is a reviewed record in tables, projected into AGE |
