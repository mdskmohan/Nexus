# ADR-001: Tenant isolation with Postgres row-level security

**Status:** Accepted · 2026-09-26

## Context
A law firm's matter files are among the most sensitive data a business holds.
Isolation between firms must not depend on every query remembering a
`WHERE firm_id = …`.

## Decision
Every tenant table carries `firm_id` and has `ENABLE` + `FORCE ROW LEVEL
SECURITY` with a policy keyed on the transaction-local setting `app.firm_id`.
The application connects as `nexus_app`, which owns nothing and cannot bypass
RLS; migrations run as `nexus_owner`. All work happens inside `db.tenant()`,
which sets the firm for the transaction.

Two documented exceptions: the `jobs` table (the worker claims across firms,
then switches into the job's firm) and a `SECURITY DEFINER` login lookup that
returns only what login needs.

## Consequences
- A missing filter returns nothing from another firm, and cross-firm writes
  fail. Both are covered by tests.
- Every connection must set `app.firm_id`; forgetting it yields empty results,
  never another firm's data (fail closed).
- Cross-firm analytics require the owner role, deliberately.
