# ADR-011: The knowledge graph is a reviewed record in tables, projected into AGE

Status: accepted (2026-10-16). Refines ADR-003.

## Context

ADR-003 put the knowledge graph in Apache AGE. Building M1 showed three things the graph store itself is
poor at: review status per item, reproducing any past version, and isolation between workspaces that the
database enforces (AGE's label tables are created on the fly and hold properties as `agtype`, so row-level
security does not fit them).

## Decision

- **The record is relational.** `kg_items` holds every table, column, join, entity and metric with its review
  status, origin and evidence; `kg_versions` holds one row per approved change. Both are tenant tables under
  row-level security. An item is in version N when `approved_in <= N` and it was not deprecated by N.
- **AGE holds the approved graph, for traversal.** Approving or retiring items writes the change to AGE in the
  same transaction: tables become `Table` nodes, joins `JOINS` edges, metrics and entities their own nodes.
  Every element carries `in_v` and `out_v`, so join paths can be found as of any version.
- **One graph per workspace, reachable only through `kg_cypher`.** The app role has no privilege on any graph
  schema. `kg_cypher` is a `SECURITY DEFINER` function that derives the graph name from `app.workspace_id`, the
  same setting row-level security uses, so no code path can name another workspace's graph.

## Costs

AGE 1.6 lacks `all()` and list comprehensions over path elements, so version filtering of a path's joins is
done in Python after collecting each path's joins with `collect()`.
