"""OpenLineage event ingestion.

Nexus is the collector. Airflow, Spark, dbt and Dagster all emit OpenLineage
RunEvents, so one implementation yields runtime lineage from every engine that
speaks the standard — which is why it earns P0 status (ADR-005).

Runtime lineage differs from the static lineage a dbt manifest gives us: it
records what a job *actually read and wrote on a particular run*, not what the
code says it should. When those disagree, the disagreement is itself evidence.

Events are push-based, so for pipelines Nexus deploys we wire the listener in at
deploy time and lineage is automatic. For an adopted estate the customer must
enable it themselves.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from nexus.graph.entities import Edge, EdgeKind, Node, NodeKind

SYSTEM = "openlineage"

#: Terminal event types. A run is only complete evidence once one of these lands.
TERMINAL_EVENTS = frozenset({"COMPLETE", "FAIL", "ABORT"})

#: Event types that indicate the run did not succeed.
FAILURE_EVENTS = frozenset({"FAIL", "ABORT"})


def _dataset_id(namespace: str, name: str) -> str:
    """Stable id for a dataset across every engine that reports it.

    The namespace identifies the storage system (a warehouse URI), so the same
    physical table reported by Airflow and by Spark resolves to one node rather
    than two.
    """
    return f"{SYSTEM}:dataset:{namespace}/{name}".lower()


def _job_id(namespace: str, name: str) -> str:
    return f"{SYSTEM}:job:{namespace}/{name}"


@dataclass(slots=True)
class RunEvent:
    """One OpenLineage event, reduced to the fields Nexus acts on."""

    event_type: str
    event_time: datetime | None
    run_id: str
    job_namespace: str
    job_name: str
    inputs: list[tuple[str, str]] = field(default_factory=list)
    outputs: list[tuple[str, str]] = field(default_factory=list)
    producer: str = ""
    #: Present on FAIL events that carry an errorMessage facet.
    error_message: str | None = None

    @property
    def is_terminal(self) -> bool:
        return self.event_type in TERMINAL_EVENTS

    @property
    def failed(self) -> bool:
        return self.event_type in FAILURE_EVENTS


def _parse_time(raw: Any) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _datasets(payload: Any) -> list[tuple[str, str]]:
    """Extract (namespace, name) pairs from an inputs/outputs array."""
    if not isinstance(payload, list):
        return []
    pairs: list[tuple[str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        namespace, name = item.get("namespace"), item.get("name")
        if isinstance(namespace, str) and isinstance(name, str):
            pairs.append((namespace, name))
    return pairs


def parse_event(payload: dict[str, Any]) -> RunEvent | None:
    """Parse a raw OpenLineage event, or None if it is not usable.

    Returns None rather than raising: a malformed event from one engine must not
    reject the whole batch, and events arrive from systems we do not control.
    """
    run = payload.get("run") or {}
    job = payload.get("job") or {}
    run_id = run.get("runId")
    job_name = job.get("name")
    if not isinstance(run_id, str) or not isinstance(job_name, str):
        return None

    error = None
    facets = run.get("facets") or {}
    if isinstance(facets, dict):
        err_facet = facets.get("errorMessage")
        if isinstance(err_facet, dict):
            message = err_facet.get("message")
            if isinstance(message, str):
                error = message

    return RunEvent(
        event_type=str(payload.get("eventType") or "OTHER").upper(),
        event_time=_parse_time(payload.get("eventTime")),
        run_id=run_id,
        job_namespace=str(job.get("namespace") or "default"),
        job_name=job_name,
        inputs=_datasets(payload.get("inputs")),
        outputs=_datasets(payload.get("outputs")),
        producer=str(payload.get("producer") or ""),
        error_message=error,
    )


class LineageStore:
    """In-memory accumulation of lineage from received events.

    Deliberately in-memory for now: persistence needs a storage decision that has
    not been made, and pretending otherwise would hide the gap. Everything here
    is replaceable by a repository interface without changing callers.
    """

    def __init__(self) -> None:
        self._events: list[RunEvent] = []

    def record(self, event: RunEvent) -> None:
        self._events.append(event)

    @property
    def event_count(self) -> int:
        return len(self._events)

    def runs(self) -> dict[str, list[RunEvent]]:
        """Events grouped by run id, in arrival order."""
        grouped: dict[str, list[RunEvent]] = {}
        for event in self._events:
            grouped.setdefault(event.run_id, []).append(event)
        return grouped

    def failures(self) -> list[RunEvent]:
        """Every event reporting a failed run."""
        return [e for e in self._events if e.failed]

    def graph(self) -> tuple[list[Node], list[Edge]]:
        """Build nodes and edges from everything received so far.

        Edge direction follows data flow: input dataset -> job -> output dataset,
        so downstream impact stays a forward traversal, matching every other
        connector.
        """
        nodes: dict[str, Node] = {}
        edges: set[tuple[str, str, EdgeKind]] = set()

        for event in self._events:
            job_id = _job_id(event.job_namespace, event.job_name)
            nodes.setdefault(
                job_id,
                Node(
                    id=job_id,
                    kind=NodeKind.TASK,
                    name=event.job_name,
                    system=SYSTEM,
                    attributes={
                        "namespace": event.job_namespace,
                        "producer": event.producer,
                    },
                ),
            )

            for namespace, name in event.inputs:
                ds_id = _dataset_id(namespace, name)
                nodes.setdefault(
                    ds_id,
                    Node(
                        id=ds_id,
                        kind=NodeKind.SOURCE,
                        name=name,
                        system=SYSTEM,
                        attributes={"namespace": namespace},
                    ),
                )
                edges.add((ds_id, job_id, EdgeKind.DEPENDS_ON))

            for namespace, name in event.outputs:
                ds_id = _dataset_id(namespace, name)
                nodes.setdefault(
                    ds_id,
                    Node(
                        id=ds_id,
                        kind=NodeKind.SOURCE,
                        name=name,
                        system=SYSTEM,
                        attributes={"namespace": namespace},
                    ),
                )
                edges.add((job_id, ds_id, EdgeKind.DEPENDS_ON))

        return (
            list(nodes.values()),
            [Edge(source=s, target=t, kind=k) for s, t, k in sorted(edges)],
        )
