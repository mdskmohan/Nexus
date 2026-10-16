# ADR-006: Our own agent runtime; no external agent frameworks

Status: accepted (2026-10-16)

## Decision

The runtime that executes agent specs is ours, built on the durable run and job queue (ADR-007). It does not
use LangChain, LangGraph, CrewAI or similar.

## Why

What we sell is the safety layer around each step: validation against the approved graph, the user's own
permissions, approvals, number verification and a complete record. That layer has to own the execution loop.
The durable runs from the previous product (stop, spending limits, crash recovery, step log) already cover the
core of an orchestrator, and keep the runtime model-neutral through our own adapters.

## Costs

Features a framework would give for free (some node types, integrations) are built by us, when needed.
