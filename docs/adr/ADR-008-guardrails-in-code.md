# ADR-008: Guardrails enforced in code

Status: accepted (2026-10-16)

## Decision

Safety rules are checked by code around every step, not requested in a prompt, and no agent spec can turn
them off:

- **Read-only SQL.** Queries are parsed with sqlglot; anything but a read is rejected.
- **Only approved context.** Every table, column, join and metric must exist in the approved knowledge graph.
- **The user's own permissions.** Queries run with the requesting user's warehouse permissions.
- **Limits.** Cost estimate, row limit, step, token and spending limits per run.
- **Number verification.** Every number in an answer must trace to a cell of a query result; anything that
  does not is removed or visibly marked.
- **Approvals required by policy**, workspace isolation, and the audit trail.

## Why

A prompt can be ignored or overridden by text in the data. A check in code cannot.
