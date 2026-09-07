"""Connector configuration endpoints.

Serves the catalogue the connections UI renders, and probes configurations the
user submits. Configurations are not persisted here — storing customer
credentials needs an encrypted store and a key management decision, which is its
own piece of work. Until then this endpoint proves a configuration works and
returns; it never writes secrets to disk.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from nexus.api.schemas import (
    ConnectionTestRequest,
    ConnectionTestResponse,
    ConnectorSchema,
)
from nexus.connectors import registry

router = APIRouter(prefix="/api/v1", tags=["connectors"])


@router.get("/connectors", response_model=list[ConnectorSchema])
def list_connectors() -> list[ConnectorSchema]:
    """Every platform Nexus can connect to, with the fields each requires."""
    return [
        ConnectorSchema.from_spec(spec, registry.driver_available(spec))
        for spec in registry.all_specs()
    ]


@router.get("/connectors/{connector_id}", response_model=ConnectorSchema)
def get_connector(connector_id: str) -> ConnectorSchema:
    """One platform's configuration schema."""
    try:
        spec = registry.get_spec(connector_id)
    except registry.UnknownConnector as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ConnectorSchema.from_spec(spec, registry.driver_available(spec))


@router.post("/connections/test", response_model=ConnectionTestResponse)
def test_connection(request: ConnectionTestRequest) -> ConnectionTestResponse:
    """Probe a configuration against the real platform.

    Always returns 200 with ``ok`` set, rather than raising for a failed
    connection: a wrong password is an expected outcome of this endpoint, not a
    server error, and the UI needs the message either way.
    """
    try:
        result = registry.test_connection(request.connector_id, request.config)
    except registry.UnknownConnector as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ConnectionTestResponse(
        ok=result.ok, message=result.message, details=result.details
    )
