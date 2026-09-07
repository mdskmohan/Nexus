"""OpenLineage receiver.

Airflow, Spark and dbt POST RunEvents here. The endpoint is deliberately
permissive about event shape: events arrive from systems Nexus does not control,
and rejecting a batch because one engine added a field would lose lineage for
reasons that are not the customer's fault.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, status

from nexus.connectors.openlineage import LineageStore, parse_event

router = APIRouter(prefix="/api/v1", tags=["lineage"])

#: Process-local for now. Persistence is a storage decision not yet made, and a
#: fake durable store would hide that gap. Swappable for a repository without
#: changing this module's callers.
STORE = LineageStore()


@router.post("/lineage", status_code=status.HTTP_202_ACCEPTED)
async def receive_lineage(request: Request) -> dict[str, Any]:
    """Accept one OpenLineage RunEvent.

    Always accepts. An unparseable event is counted and dropped rather than
    returning an error, because an emitter that starts getting 4xx responses will
    often disable itself, and losing all lineage is worse than losing one event.
    """
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001 - malformed body from an external emitter
        return {"accepted": False, "reason": "body was not valid JSON"}

    if not isinstance(payload, dict):
        return {"accepted": False, "reason": "event was not a JSON object"}

    event = parse_event(payload)
    if event is None:
        return {"accepted": False, "reason": "event lacked a run id or job name"}

    STORE.record(event)
    return {
        "accepted": True,
        "run_id": event.run_id,
        "job": f"{event.job_namespace}/{event.job_name}",
        "event_type": event.event_type,
    }


@router.get("/lineage/summary")
def lineage_summary() -> dict[str, Any]:
    """What the collector has received so far.

    Exists so the stack can be verified end to end: trigger a DAG, call this, and
    see whether events actually arrived.
    """
    nodes, edges = STORE.graph()
    return {
        "events_received": STORE.event_count,
        "runs": len(STORE.runs()),
        "failures": len(STORE.failures()),
        "nodes": len(nodes),
        "edges": len(edges),
    }


@router.get("/lineage/graph")
def lineage_graph() -> dict[str, Any]:
    """The lineage graph assembled from received events."""
    nodes, edges = STORE.graph()
    return {
        "nodes": [
            {
                "id": n.id,
                "kind": n.kind.value,
                "name": n.name,
                "system": n.system,
                "attributes": n.attributes,
            }
            for n in nodes
        ],
        "edges": [
            {"source": e.source, "target": e.target, "kind": e.kind.value} for e in edges
        ],
    }
