# ADR-006: The conversational surface is a policy client, not a second path

- **Status:** Accepted
- **Date:** 2026-09-05

## Context

The primary users are data engineers, and the intended primary interaction is
conversational: describe a data product and have Nexus build it, then ask it to manage,
monitor, diagnose and repair what it built. The full lifecycle is in scope — create,
deploy, manage, monitor, diagnose, fix, archive, delete.

A chat surface that can act on production infrastructure is the most dangerous component
in the system. It is also the one most likely to be built as a shortcut, because wiring a
model directly to a database client is a afternoon's work and looks like a demo.

## Decision

**The copilot is a client of the policy engine with no privileges of its own.** Its tool
surface is exactly the action catalogue defined in ADR-003, and every tool invocation is
gated identically to one initiated from a button in the UI. There is no code path from
the conversation to a customer system that skips the gate.

Concretely:

- The model emits a typed action, never SQL or shell against a live system.
- The action is resolved against the catalogue, assigned its required autonomy level,
  and gated. A blocked action returns an explanation, not a failure.
- Read-only questions ("what feeds this table", "why did this fail") need no gate and
  should feel instant. The gate exists for actions, not answers.
- Every conversational action lands in the same audit trail as a UI-initiated one, marked
  by origin.

**Chat complements the structured UI; it does not replace it.** Lineage, run history and
impact are inherently visual, and a data engineer does not want to converse with a
dependency graph. The conversation's job is to *drive* those surfaces — answer, then deep
link into the view that shows the evidence. A copilot that renders lineage as prose has
made the product worse.

**Lifecycle operations inherit their autonomy levels from the action class, not from the
interface.** Creation of a new pipeline in a sandbox is low risk; deletion of a
production dataset remains human-only regardless of how confidently it was requested.
Archiving is reversible and therefore gateable; deletion is not.

## Consequences

**Good.** The copilot cannot become a privilege-escalation path, and it needs no separate
security review — reviewing the action catalogue covers both surfaces. It also forces the
action catalogue to be genuinely complete and well-typed, which the UI benefits from.

**Costly.** Every capability must be modelled as a typed action before the copilot can
perform it. There is no "just let the model run this query" escape hatch, so some
capabilities land later than they would with a direct integration.

**Watch for.** The temptation, under demo pressure, to give the conversation a raw SQL
tool "temporarily". That single change would invalidate ADR-003 and the security posture
of the whole product.

## Alternatives considered

- **Give the model direct execution with a strong system prompt.** Rejected. A prompt is
  not an enforcement boundary; this is already settled in ADR-003.
- **A chat-only interface, no structured UI.** Rejected. Monitoring and lineage are
  visual problems, and forcing them through prose would make the product worse for its
  primary user.
- **A separate, more permissive action set for chat.** Rejected outright — it is exactly
  the privilege-escalation path this ADR exists to prevent.
