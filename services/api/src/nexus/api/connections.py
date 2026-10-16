"""Warehouse connections: add, test, collect metadata."""

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from nexus import audit, connections, jobs
from nexus.ai.secrets import SecretError
from nexus.api.deps import Principal, db, found, require, require_any
from nexus.connectors import KINDS, ConnectorError
from nexus.db import row, rows, scalar
from nexus.graph.collect import JOB_KIND as COLLECT

router = APIRouter(prefix="/api/connections", tags=["connections"])

# People who build on the knowledge graph or review it can see connections; only admins change them.
VIEW = require_any("manage_connections", "approve_graph", "build_agents")
MANAGE = require("manage_connections")


class NewConnection(BaseModel):
    kind: str
    label: str = Field(min_length=1, max_length=200)
    values: dict[str, str] = Field(default_factory=dict)


class ConnectionUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=200)
    # Secret fields left blank keep their saved value.
    values: dict[str, str] | None = None


def _public(conn: dict, workspace_id: str) -> dict:
    spec = KINDS[conn["kind"]].spec
    saved = {f.name for f in spec.fields if f.secret} & set(_secrets(conn, workspace_id))
    out = {k: conn[k] for k in ("id", "kind", "label", "config", "last_test_ok", "last_test_at", "last_test_msg",
                                "collect_status", "collected_at", "collect_msg", "created_at")}
    out["secrets_saved"] = sorted(saved)
    out["verified"] = spec.verified
    return out


def _secrets(conn: dict, workspace_id: str) -> dict:
    try:
        return connections.unseal(conn["secrets_enc"], workspace_id)
    except SecretError:
        return {}


def _seal(values: dict, workspace_id: str) -> str | None:
    try:
        return connections.seal(values, workspace_id)
    except SecretError as exc:
        raise HTTPException(503, "Nexus cannot store credentials yet: the server's encryption key is not set.") from exc


@router.get("/kinds")
def kinds(who: Principal = Depends(VIEW)) -> list[dict]:
    return [k.spec.public() for k in KINDS.values()]


@router.get("")
def list_connections(who: Principal = Depends(VIEW), s: Session = Depends(db)) -> list[dict]:
    return [_public(c, who.workspace_id) for c in rows(s, "SELECT * FROM connections ORDER BY created_at")]


@router.post("", status_code=201)
def add_connection(body: NewConnection, who: Principal = Depends(MANAGE), s: Session = Depends(db)) -> dict:
    if body.kind not in KINDS:
        raise HTTPException(422, "Unknown kind of connection.")
    spec = KINDS[body.kind].spec
    settings_, secrets_ = spec.split(body.values)
    if problems := spec.problems(settings_, secrets_):
        raise HTTPException(422, " ".join(problems))
    connection_id = scalar(s, """INSERT INTO connections (workspace_id, kind, label, config, secrets_enc, created_by)
                                 VALUES (:w, :k, :l, CAST(:c AS jsonb), :s, :u) RETURNING id""",
                           w=who.workspace_id, k=body.kind, l=body.label.strip(), c=json.dumps(settings_),
                           s=_seal(secrets_, who.workspace_id), u=who.user_id)
    audit.record(s, who.workspace_id, who.user_id, "connection.added", "connection", connection_id, kind=body.kind)
    return {"id": str(connection_id)}


@router.patch("/{connection_id}")
def update_connection(connection_id: UUID, body: ConnectionUpdate, who: Principal = Depends(MANAGE),
                      s: Session = Depends(db)) -> dict:
    conn = found(row(s, "SELECT * FROM connections WHERE id = :c", c=connection_id), "No such connection.")
    if body.values is not None:
        spec = KINDS[conn["kind"]].spec
        settings_, secrets_ = spec.split(body.values)
        secrets_ = {**_secrets(conn, who.workspace_id), **secrets_}
        if problems := spec.problems(settings_, secrets_):
            raise HTTPException(422, " ".join(problems))
        scalar(s, """UPDATE connections SET config = CAST(:c AS jsonb), secrets_enc = :s, last_test_ok = NULL
                     WHERE id = :i RETURNING id""",
               c=json.dumps(settings_), s=_seal(secrets_, who.workspace_id), i=connection_id)
    if body.label:
        scalar(s, "UPDATE connections SET label = :l WHERE id = :i RETURNING id", l=body.label.strip(), i=connection_id)
    audit.record(s, who.workspace_id, who.user_id, "connection.updated", "connection", connection_id,
                 settings_changed=body.values is not None)
    return {"ok": True}


@router.delete("/{connection_id}")
def delete_connection(connection_id: UUID, who: Principal = Depends(MANAGE), s: Session = Depends(db)) -> dict:
    found(row(s, "SELECT id FROM connections WHERE id = :c", c=connection_id), "No such connection.")
    if scalar(s, "SELECT count(*) FROM kg_items WHERE connection_id = :c AND status = 'approved'", c=connection_id):
        raise HTTPException(409, "Tables from this connection are in the knowledge graph. "
                                 "Ask a steward to remove them first.")
    scalar(s, "DELETE FROM connections WHERE id = :c RETURNING id", c=connection_id)
    audit.record(s, who.workspace_id, who.user_id, "connection.removed", "connection", connection_id)
    return {"ok": True}


@router.post("/{connection_id}/test")
def test_connection(connection_id: UUID, who: Principal = Depends(MANAGE), s: Session = Depends(db)) -> dict:
    conn = found(row(s, "SELECT * FROM connections WHERE id = :c", c=connection_id), "No such connection.")
    try:
        with connections.open_warehouse(who.workspace_id, conn) as wh:
            result = wh.test()
        ok, message, details = result.ok, result.message, result.details
    except ConnectorError as exc:
        ok, message, details = False, f"Could not connect: {exc}", {}
    scalar(s, """UPDATE connections SET last_test_ok = :ok, last_test_at = now(), last_test_msg = :m
                 WHERE id = :c RETURNING id""", ok=ok, m=message[:500], c=connection_id)
    audit.record(s, who.workspace_id, who.user_id, "connection.tested", "connection", connection_id, ok=ok)
    return {"ok": ok, "message": message, "details": details}


@router.post("/{connection_id}/collect")
def collect(connection_id: UUID, who: Principal = Depends(MANAGE), s: Session = Depends(db)) -> dict:
    conn = found(row(s, "SELECT collect_status FROM connections WHERE id = :c", c=connection_id), "No such connection.")
    if conn["collect_status"] in ("queued", "running"):
        raise HTTPException(409, "Nexus is already reading this connection.")
    scalar(s, "UPDATE connections SET collect_status = 'queued' WHERE id = :c RETURNING id", c=connection_id)
    jobs.enqueue(s, who.workspace_id, COLLECT, {"connection_id": str(connection_id)}, max_attempts=1)
    audit.record(s, who.workspace_id, who.user_id, "connection.collect_requested", "connection", connection_id)
    return {"ok": True}
