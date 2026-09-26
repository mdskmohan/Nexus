# ADR-002: Verify every citation in code before a lawyer sees it

**Status:** Accepted · 2026-09-26

## Context
The defining failure of legal AI is a confident statement backed by a source
that does not exist or does not say what is claimed. Lawyers have been
sanctioned for filing AI-invented citations. Prompting a model to "only cite
real sources" reduces this but does not prevent it.

## Decision
Agents must attach, to each statement, a passage id and the exact words relied
on. Deterministic code checks each quote against the stored passage text
(normalising only typography, whitespace and case, with ellipsis support). Work
that fails is sent back to the agent with the specific failures. Anything that
still fails is removed (answers) or visibly marked `[unverified]` (drafts), and
counted.

## Consequences
- "✓ Checked" has a precise, testable meaning.
- No fuzzy matching: a quote with one word changed fails. This causes some
  send-backs, which cost tokens.
- The check proves provenance, not interpretation. The lawyer still judges
  whether the quote supports the statement; the product says so plainly.
