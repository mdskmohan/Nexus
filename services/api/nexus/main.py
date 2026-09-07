"""Nexus API.

The control plane's HTTP surface. Two things live here today: the connector
catalogue the connections UI renders, and the OpenLineage receiver that Airflow
and Spark emit to.

Deliberately absent: any endpoint that changes a customer system. Those are
actions, and actions go through the policy engine (ADR-003).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nexus.api import connectors, lineage

app = FastAPI(
    title="Nexus",
    description="The AI control plane for enterprise data engineering",
    version="0.1.0",
)

# The web client is served from a different origin in development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(connectors.router)
app.include_router(lineage.router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "service": "nexus-api"}
