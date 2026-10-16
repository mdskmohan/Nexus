# ADR-009: Combine results across warehouses in DuckDB

Status: accepted (2026-10-16)

## Decision

Each query runs in its own warehouse. When a plan joins results from more than one warehouse, the bounded
result sets are combined in **DuckDB** inside the worker. We do not use a query-federation layer.

## Why

DuckDB is embedded, fast and open source, needs no extra service, and keeps each warehouse's own permissions
in force for the part of the query that touches it.

## Costs

Results must be small enough to move: row limits apply, and agents are steered to aggregate in each warehouse
before combining.
