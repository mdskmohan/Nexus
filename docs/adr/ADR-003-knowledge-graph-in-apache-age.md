# ADR-003: Knowledge graph in Apache AGE, behind one graph interface

Status: accepted (2026-10-16)

## Context

The knowledge graph needs graph queries: join paths between entities across warehouses, and lineage impact
("what breaks if this model changes"). The store must be open source.

| Option | License | Why not (for now) |
|---|---|---|
| Neo4j Community | GPLv3 | Second database to secure and keep in step with approvals; no built-in tenant isolation; multiple databases and access roles need Enterprise |
| JanusGraph, NebulaGraph | Apache 2.0 | Distributed systems built for far larger graphs than ours |
| Memgraph, ArangoDB, FalkorDB | BSL / SSPL | Source-available, not open source |

## Decision

Use **Apache AGE** (Apache 2.0), which adds Cypher queries to Postgres. All graph access goes through one
internal interface (`nexus.graph`), which always scopes by workspace and graph version.

## Why

One database: approvals and graph changes commit in the same transaction, and row-level security keeps
isolating workspaces. Cypher keeps join-path and lineage queries readable.

## Costs

AGE is less mature than Neo4j, has no graph-algorithm library, and is not offered by every managed Postgres
service. The interface keeps a move to Neo4j open if traversal performance or algorithms demand it.
