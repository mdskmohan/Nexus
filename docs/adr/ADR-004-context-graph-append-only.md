# ADR-004: Context graph as append-only Postgres tables

Status: accepted (2026-10-16)

## Decision

The context graph (questions, plans, queries, approvals, corrections, exceptions) is stored in append-only
Postgres tables, each record linked to the knowledge-graph nodes it touched and the graph version in force.
It is not stored in the graph database.

## Why

Records are only ever added, and are read by time, by run and by entity. That is a table's job. Keeping them
next to runs and approvals means a decision and its record commit together.

## Costs

Questions that walk from a decision across the knowledge graph join the two stores. That is done in the graph
interface (ADR-003).
