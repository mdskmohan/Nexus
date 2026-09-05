"""Environment graph entities.

The graph is what connectors populate and the diagnosis engine walks. It is
deliberately system-agnostic: a node knows which system reported it, but the
traversal code never branches on vendor.

Node ids are namespaced by system (``dbt:model.shop.stg_orders``) so two
connectors can never collide. Joining a node across systems — recognising that
an Airflow task *runs* a particular dbt model — is a separate, explicit step,
because that inference is exactly where a lifted graph goes quietly wrong.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class NodeKind(StrEnum):
    """What a graph node represents."""

    SOURCE = "source"
    MODEL = "model"
    TEST = "test"
    DAG = "dag"
    TASK = "task"
    CONSUMER = "consumer"


class EdgeKind(StrEnum):
    """How two nodes relate.

    Direction is always *from depends on / acts on to*, so downstream impact is
    a forward traversal from the failing node.
    """

    #: target is built from source (data flows source -> target)
    DEPENDS_ON = "depends_on"
    #: an orchestrator node executes a transformation node
    EXECUTES = "executes"
    #: a test asserts something about a node
    TESTS = "tests"
    #: a consumer reads a node
    READS = "reads"


@dataclass(frozen=True, slots=True)
class Node:
    """One entity in the environment graph."""

    id: str
    kind: NodeKind
    name: str
    #: Which connector reported this node, e.g. "dbt".
    system: str
    #: Free-form, system-specific detail. Never interpreted by traversal code.
    attributes: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if ":" not in self.id:
            raise ValueError(f"node id {self.id!r} must be namespaced as '<system>:<local id>'")


@dataclass(frozen=True, slots=True)
class Edge:
    """A directed relationship between two nodes."""

    source: str
    target: str
    kind: EdgeKind

    def __post_init__(self) -> None:
        if self.source == self.target:
            raise ValueError(f"self-referential edge on {self.source!r}")
