# ADR-001: Python and FastAPI for the backend; Next.js for the web app

Status: accepted (2026-10-16)

## Context

The hard part of Nexus is understanding and safely running SQL across different warehouses, and analysing the
results. The web app, and above all the visual builder, is TypeScript work. We considered one language
(TypeScript and Node.js) end to end.

## Decision

The API, worker and agent runtime are **Python 3.12 with FastAPI**. The web app is **Next.js** with
**React Flow** for the canvas.

## Why

- **sqlglot** parses and translates about 30 SQL dialects, including Snowflake and Databricks. Read-only
  checks, table and column extraction and dialect translation depend on it. Nothing comparable exists for
  Node.js.
- The official Snowflake and Databricks drivers, DuckDB, and the analysis libraries (pandas, polars, scipy,
  statsmodels) are first-class in Python.
- The code we reuse (model adapters, durable runs, audit, warehouse connectors) is Python.
- The AI provider SDKs are equally good in both languages.

## Costs

Two languages. The agent spec and node schemas are shared between canvas and runtime, so they are defined once
as JSON Schema and both Pydantic models and TypeScript types are generated from it (see ADR-005).
