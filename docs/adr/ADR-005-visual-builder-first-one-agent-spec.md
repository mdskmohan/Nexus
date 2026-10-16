# ADR-005: Visual builder first; one versioned agent spec for canvas, runtime and SDK

Status: accepted (2026-10-16)

## Decision

Agents are built inside Nexus, in **Agent Studio**. The visual builder comes first and the SDK later. Every
agent is saved as a versioned **agent spec** (JSON): nodes, edges, node settings and policies. The canvas
reads and writes the spec, the runtime executes it, and the SDK, later, writes it too.

The spec and each node type's settings are defined once as **JSON Schema**. Pydantic models (runtime) and
TypeScript types (canvas) are generated from it. Canvas layout (positions, zoom) is stored apart from the
logic, so moving a box is not a new version of the agent.

## Why

One definition means the SDK adds no second execution path, and anything built on the canvas can later be
written in code and the other way round.

## Costs

The spec format is a public contract once the SDK ships, so changes to it are versioned.

## Not doing

Running agents built in other platforms. Flowise was read for interface ideas only; no code is copied.
