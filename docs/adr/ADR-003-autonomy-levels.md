# ADR-003: Autonomy levels and the execution boundary

- **Status:** Accepted
- **Date:** 2026-09-05

## Context

Nexus proposes changes to production data infrastructure. The reasoning behind those
changes comes from a language model, which is probabilistic and occasionally confidently
wrong. The hardest question a buyer will ask is not "is this useful" — engineers see that
immediately — but "can I trust it in production."

Trust cannot be claimed in a pitch. It has to be structurally enforced and then earned
over time.

## Decision

**The model never executes.** It emits a proposed action as data. A deterministic policy
engine decides whether that action may run, and a separate execution layer runs it. There
is no code path from model output to a customer system that skips the policy engine.

Actions are classified and gated by autonomy level:

| Level | Name | The system may |
| --- | --- | --- |
| 0 | Observe | Read state only |
| 1 | Recommend | Propose a change in the UI |
| 2 | Prepare | Open a PR or draft a config change |
| 3 | Execute with approval | Run after a human approves |
| 4 | Autonomous | Run without approval, for approved action classes only |

Default gating by action class:

| Action | Level |
| --- | --- |
| Retry a transient failure | 4 |
| Restart a failed task | 4 |
| Diagnose schema drift | 4 |
| Open a remediation PR | 4 |
| Modify a transformation | 3 |
| Change a production schema | 3 |
| Backfill a large dataset | 3 |
| Delete data | Human only — never automated |

Levels are configured per customer, per environment, and per action class. A customer
starts at level 1 and moves up as their own incident history gives them reason to.

## Consequences

**Good.** The gate is a product feature, not just a safety mechanism — it is a large part
of what a customer is buying, and it is the honest answer to "why not just point Claude at
this." It also gives us a clean, auditable record of every action considered and taken.

**Costly.** Every new capability needs an action class and a policy decision before it can
ship. This deliberately slows feature work, which is the intent.

**Constraint.** Level 4 requires that an action be reversible or trivially re-runnable.
Any action that fails that test cannot be assigned level 4 regardless of customer appetite.

## Alternatives considered

- **A single global autonomy setting.** Too blunt. Customers want automated retries long
  before they want automated schema changes.
- **Model-side guardrails via prompting.** Rejected outright. A prompt is not an
  enforcement boundary.
