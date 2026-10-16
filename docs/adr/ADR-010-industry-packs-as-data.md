# ADR-010: Industry packs loaded as data, built later

Status: accepted (2026-10-16)

## Decision

The platform is built horizontally first. Ontologies, metric libraries, join templates, agent templates and
guardrail rules are always loaded as data, never written into the code. Later, an **industry pack** bundles
these for one industry (pharma commercial analytics was discussed) and plugs in without changing the core.

## Why

It keeps the option of leading with one industry open at almost no cost now.
