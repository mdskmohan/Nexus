# ADR-007: Human-in-the-loop as durable run states

Status: accepted (2026-10-16)

## Decision

A run that needs a person moves to the state **`waiting`**. Its progress is saved, its worker job ends, and
the run holds no memory or connection while a person decides. When the person answers, a new job resumes the
run from the saved point. Approvals are records with who, when, what was shown, the decision and the graph
version; each is written to the audit trail and, from M3, to the context graph.

Checkpoints: knowledge-graph changes (steward, always); plan approval (when policy requires: across
warehouses, sensitive data, over a cost limit, an unapproved join); clarification (when the agent is not
confident); review before publishing (set per agent); actions that write (always); corrections (always
available).

## Why

People take minutes or days to answer. A pause that lives in memory is lost on every restart, and a worker
blocked on a person cannot do other work.

## Costs

Every step that can pause must save enough state to resume, and resuming must not repeat paid or side-effecting
work. The runtime records which steps are complete for that reason.
