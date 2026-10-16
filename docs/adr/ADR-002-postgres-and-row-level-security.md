# ADR-002: Postgres as the system of record; tenants isolated by row-level security

Status: accepted (2026-10-16)

## Decision

Postgres holds workspaces, people, AI settings, runs, approvals, the audit trail and the context graph, and
hosts the knowledge graph (ADR-003). Every tenant table has `workspace_id` and a row-level security policy on
the transaction setting `app.workspace_id`, with `FORCE ROW LEVEL SECURITY`. The API and worker connect as
`nexus_app`, which does not own the tables. Migrations run as `nexus_owner`.

## Why

Isolation between customers must not depend on every query remembering a `WHERE` clause. A query that
forgets one still sees only its own workspace's rows, and a write into another workspace is rejected by the
database. This was proven in the previous product and its tests are carried over.

## Costs

Two code paths step around the policies, deliberately and narrowly: the job queue (which the worker reads
across workspaces before switching into the job's workspace) and the sign-in lookup function (which must find
a user before it knows their workspace).
