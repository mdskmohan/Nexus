# ADR-003: Our own agent loop on the Claude Messages API

**Status:** Accepted · 2026-09-26

## Context
We need agents that research documents with tools and produce checked work
product. Options: an agent framework, a hosted agent service, or a small loop
we own on the Messages API.

## Decision
A small loop (`agents/base.py`) on the Messages API with client-side tools. It
records every tool call as a plain-language step, meters tokens and cost,
enforces step and spending limits, never retries paid work automatically, and
lets finishing tools reject output with specific, fixable errors.

Defaults: `claude-opus-5`, adaptive thinking, effort `high`, automatic prompt
caching, strict tool schemas, server-side refusal fallbacks.

## Consequences
- Every guardrail sits on the only path between the model and the database.
- The conversation is append-only, which keeps caching effective and thinking
  blocks valid.
- We maintain the loop ourselves (under 200 lines).
