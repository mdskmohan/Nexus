"""The knowledge graph: browse it, propose metrics and entities, and review proposals."""

import json
import re
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from nexus import audit, jobs
from nexus.api.deps import Principal, db, found, require, require_any
from nexus.connectors import KINDS
from nexus.db import row, rows, scalar
from nexus.graph import store
from nexus.graph.joins import JOB_KIND as SUGGEST_JOINS
from nexus.graph.metrics import MetricError, validate

router = APIRouter(prefix="/api/graph", tags=["graph"])

VIEW = require_any("approve_graph", "build_agents", "manage_connections")
PROPOSE = require_any("approve_graph", "build_agents")
REVIEW = require("approve_graph")

_ITEM_COLUMNS = """i.id, i.kind, i.key, i.name, i.description, i.attrs, i.status, i.origin, i.connection_id,
                   i.parent_id, i.approved_in, i.deprecated_in, i.missing_since, i.review_note, i.reviewed_at,
                   i.created_at, c.label AS connection_label, r.name AS reviewed_by_name, p.name AS proposed_by_name"""
_ITEM_FROM = """kg_items i LEFT JOIN connections c ON c.id = i.connection_id
                LEFT JOIN users r ON r.id = i.reviewed_by LEFT JOIN users p ON p.id = i.proposed_by"""


class Review(BaseModel):
    item_ids: list[UUID] = Field(min_length=1, max_length=2000)
    decision: Literal["approve", "reject"]
    note: str | None = Field(default=None, max_length=2000)


class NewMetric(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    table_id: UUID
    measure: str = Field(min_length=1, max_length=2000)
    filter: str | None = Field(default=None, max_length=2000)


class NewEntity(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    table_ids: list[UUID] = Field(min_length=1, max_length=50)


class Describe(BaseModel):
    description: str = Field(max_length=4000)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


@router.get("/summary")
def summary(who: Principal = Depends(VIEW), s: Session = Depends(db)) -> dict:
    counts = rows(s, "SELECT kind, status, count(*) AS n FROM kg_items GROUP BY kind, status")
    out: dict = {"version": store.current_version(s), "counts": {}}
    for c in counts:
        out["counts"].setdefault(c["kind"], {})[c["status"]] = c["n"]
    out["missing"] = scalar(s, "SELECT count(*) FROM kg_items WHERE kind = 'table' AND missing_since IS NOT NULL "
                               "AND status = 'approved'")
    return out


@router.get("/items")
def list_items(kind: str | None = None, status: str | None = None, connection_id: UUID | None = None,
               q: str | None = None, who: Principal = Depends(VIEW), s: Session = Depends(db)) -> list[dict]:
    return rows(s, f"""SELECT {_ITEM_COLUMNS} FROM {_ITEM_FROM}
                       WHERE (CAST(:k AS text) IS NULL OR i.kind = :k)
                         AND (CAST(:st AS text) IS NULL OR i.status = :st)
                         AND (CAST(:c AS uuid) IS NULL OR i.connection_id = :c)
                         AND (CAST(:q AS text) IS NULL OR i.name ILIKE '%' || :q || '%')
                       ORDER BY i.kind, i.name LIMIT 1000""",
                k=kind, st=status, c=connection_id, q=q)


@router.get("/items/{item_id}")
def get_item(item_id: UUID, who: Principal = Depends(VIEW), s: Session = Depends(db)) -> dict:
    item = found(row(s, f"SELECT {_ITEM_COLUMNS} FROM {_ITEM_FROM} WHERE i.id = :i", i=item_id), "No such item.")
    if item["kind"] == "table":
        item["columns"] = rows(s, """SELECT id, name, description, attrs, status, missing_since FROM kg_items
                                     WHERE parent_id = :i AND kind = 'column' ORDER BY (attrs->>'ordinal')::int""",
                               i=item_id)
        item["joins"] = rows(s, """SELECT id, name, status, attrs FROM kg_items WHERE kind = 'join'
                                   AND (attrs->>'left_table_id' = :t OR attrs->>'right_table_id' = :t)
                                   ORDER BY name""", t=str(item_id))
    return item


@router.patch("/items/{item_id}")
def describe(item_id: UUID, body: Describe, who: Principal = Depends(REVIEW), s: Session = Depends(db)) -> dict:
    found(scalar(s, "UPDATE kg_items SET description = :d, updated_at = now() WHERE id = :i RETURNING id",
                 d=body.description.strip(), i=item_id), "No such item.")
    audit.record(s, who.workspace_id, who.user_id, "graph.described", "kg_item", item_id)
    return {"ok": True}


@router.post("/review")
def review(body: Review, who: Principal = Depends(REVIEW), s: Session = Depends(db)) -> dict:
    try:
        return store.review(s, who.workspace_id, who.user_id, [str(i) for i in body.item_ids], body.decision,
                            (body.note or "").strip() or None)
    except store.ReviewError as exc:
        raise HTTPException(409, str(exc)) from None


@router.post("/metrics", status_code=201)
def propose_metric(body: NewMetric, who: Principal = Depends(PROPOSE), s: Session = Depends(db)) -> dict:
    table = found(row(s, "SELECT * FROM kg_items WHERE id = :t AND kind = 'table'", t=body.table_id), "No such table.")
    if table["status"] not in ("proposed", "approved"):
        raise HTTPException(409, "This table is not in the knowledge graph.")
    conn = row(s, "SELECT kind FROM connections WHERE id = :c", c=table["connection_id"])
    columns = [r["name"] for r in rows(s, """SELECT attrs->>'column' AS name FROM kg_items
                                             WHERE parent_id = :t AND kind = 'column'""", t=body.table_id)]
    try:
        sql = validate(body.measure, body.filter, KINDS[conn["kind"]].dialect, columns)
    except MetricError as exc:
        raise HTTPException(422, str(exc)) from None
    key = f"metric:{_slug(body.name)}"
    if scalar(s, "SELECT 1 FROM kg_items WHERE kind = 'metric' AND key = :k", k=key):
        raise HTTPException(409, "A metric with this name already exists.")
    attrs = {"table_id": str(body.table_id), "table": table["name"], **sql}
    metric_id = scalar(s, """INSERT INTO kg_items (workspace_id, kind, key, connection_id, parent_id, name,
                                                   description, attrs, origin, proposed_by)
                             VALUES (:w, 'metric', :k, :c, :t, :n, :d, CAST(:a AS jsonb), 'person', :u) RETURNING id""",
                       w=who.workspace_id, k=key, c=table["connection_id"], t=body.table_id, n=body.name.strip(),
                       d=body.description.strip(), a=json.dumps(attrs), u=who.user_id)
    audit.record(s, who.workspace_id, who.user_id, "graph.metric_proposed", "kg_item", metric_id, **sql)
    return {"id": str(metric_id), **sql}


@router.post("/entities", status_code=201)
def propose_entity(body: NewEntity, who: Principal = Depends(PROPOSE), s: Session = Depends(db)) -> dict:
    ids = [str(t) for t in dict.fromkeys(body.table_ids)]
    tables = rows(s, """SELECT id, name FROM kg_items WHERE kind = 'table' AND status IN ('proposed', 'approved')
                        AND id = ANY(CAST(:t AS uuid[]))""", t=ids)
    if len(tables) != len(ids):
        raise HTTPException(422, "Choose tables that are in the knowledge graph.")
    key = f"entity:{_slug(body.name)}"
    if scalar(s, "SELECT 1 FROM kg_items WHERE kind = 'entity' AND key = :k", k=key):
        raise HTTPException(409, "An entity with this name already exists.")
    entity_id = scalar(s, """INSERT INTO kg_items (workspace_id, kind, key, name, description, attrs, origin, proposed_by)
                             VALUES (:w, 'entity', :k, :n, :d, CAST(:a AS jsonb), 'person', :u) RETURNING id""",
                       w=who.workspace_id, k=key, n=body.name.strip(), d=body.description.strip(),
                       a=json.dumps({"table_ids": ids, "tables": [t["name"] for t in tables]}), u=who.user_id)
    audit.record(s, who.workspace_id, who.user_id, "graph.entity_proposed", "kg_item", entity_id)
    return {"id": str(entity_id)}


@router.get("/versions")
def versions(who: Principal = Depends(VIEW), s: Session = Depends(db)) -> list[dict]:
    return rows(s, """SELECT v.number, v.summary, v.created_at, u.name AS created_by_name
                      FROM kg_versions v LEFT JOIN users u ON u.id = v.created_by ORDER BY v.number DESC LIMIT 200""")


@router.get("/paths")
def paths(from_table: UUID, to_table: UUID, version: int | None = None, who: Principal = Depends(VIEW),
          s: Session = Depends(db)) -> list[dict]:
    return store.join_paths(s, str(from_table), str(to_table), version)


@router.post("/suggest-joins")
def suggest_joins(who: Principal = Depends(require_any("approve_graph", "manage_connections")),
                  s: Session = Depends(db)) -> dict:
    jobs.enqueue(s, who.workspace_id, SUGGEST_JOINS, {}, max_attempts=1)
    return {"ok": True}
