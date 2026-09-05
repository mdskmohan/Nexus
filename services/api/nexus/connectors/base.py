"""Connector interface.

A connector reads one external system and emits graph entities. Connectors are
strictly read-only and strictly deterministic: no model calls, no writes, no
network retries hidden inside a parse. Anything that reaches a customer system
to *change* it lives in the execution layer behind the policy engine, never here.

Every fact a connector emits carries provenance, because the diagnosis engine
weights conclusions by how much of the underlying spec was declared versus
inferred (see ADR-001).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from nexus.graph.entities import Edge, Node


class ConnectorResult:
    """Entities recovered from one system, plus what could not be recovered.

    ``warnings`` is deliberately part of the result rather than logged and
    forgotten. When a lifted pipeline later produces a bad diagnosis, the first
    question is what the lifter failed to see, and that answer needs to survive.
    """

    def __init__(
        self,
        nodes: list[Node] | None = None,
        edges: list[Edge] | None = None,
        warnings: list[str] | None = None,
    ) -> None:
        self.nodes = nodes or []
        self.edges = edges or []
        self.warnings = warnings or []

    def __repr__(self) -> str:
        return (
            f"ConnectorResult(nodes={len(self.nodes)}, "
            f"edges={len(self.edges)}, warnings={len(self.warnings)})"
        )


@runtime_checkable
class Connector(Protocol):
    """Reads one external system and emits graph entities."""

    #: Stable identifier used in provenance strings, e.g. "dbt".
    system: str

    def collect(self) -> ConnectorResult:
        """Read the system and return everything recovered from it."""
        ...
