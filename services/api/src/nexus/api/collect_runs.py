"""Runs that read connections: history, progress, live logs, cancel and retry.

Registered before the connections router, so `/api/connections/runs` is never
taken for a connection id.
"""

import asyncio
import json
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from nexus import audit
from nexus.api.deps import Principal, db, found, require, require_any
from nexus.db import row, rows, scalar, tenant
from nexus.graph.collect import FINISHED, cancel_run, explain, start_run

router = APIRouter(prefix="/api/connections/runs", tags=["connections"])

VIEW = require_any("manage_connections", "approve_graph", "build_agents")
MANAGE = require("manage_connections")

_SELECT = """SELECT r.id, r.connection_id, r.trigger, r.status, r.phase, r.progress, r.stats, r.error, r.error_kind,
                    r.cancel_requested, r.created_at, r.started_at, r.finished_at, r.updated_at,
                    c.label AS connection_label, c.kind AS connection_kind, u.name AS requested_by_name
             FROM collect_runs r JOIN connections c ON c.id = r.connection_id
             LEFT JOIN users u ON u.id = r.requested_by"""
STREAM_POLL_SECONDS = 0.5
STREAM_HEARTBEAT_SECONDS = 15


def public(run: dict) -> dict:
    out = dict(run)
    out["hint"] = explain(run["error"])[1] if run.get("error") else None
    return out


def _run(s: Session, run_id: UUID | str) -> dict | None:
    found_run = row(s, f"{_SELECT} WHERE r.id = :r", r=str(run_id))
    return public(found_run) if found_run else None


@router.get("")
def list_runs(connection_id: UUID | None = None,
              status: str | None = Query(None, pattern="^(queued|running|succeeded|failed|cancelled|active)$"),
              before: datetime | None = None, limit: int = Query(50, ge=1, le=200),
              who: Principal = Depends(VIEW), s: Session = Depends(db)) -> list[dict]:
    where, params = ["true"], {"limit": limit}
    if connection_id:
        where.append("r.connection_id = :c")
        params["c"] = str(connection_id)
    if status == "active":
        where.append("r.status IN ('queued', 'running')")
    elif status:
        where.append("r.status = :st")
        params["st"] = status
    if before:
        where.append("r.created_at < :before")
        params["before"] = before
    return [public(r) for r in rows(s, f"{_SELECT} WHERE {' AND '.join(where)} "
                                        "ORDER BY r.created_at DESC LIMIT :limit", **params)]


@router.get("/summary")
def summary(who: Principal = Depends(VIEW), s: Session = Depends(db)) -> dict:
    counts = row(s, """SELECT count(*) FILTER (WHERE status IN ('queued', 'running')) AS active,
                              count(*) FILTER (WHERE status = 'succeeded' AND created_at > now() - interval '1 day')
                                AS succeeded_24h,
                              count(*) FILTER (WHERE status = 'failed' AND created_at > now() - interval '1 day')
                                AS failed_24h,
                              count(*) AS total
                       FROM collect_runs""")
    return {k: int(v or 0) for k, v in counts.items()}


@router.get("/{run_id}")
def get_run(run_id: UUID, who: Principal = Depends(VIEW), s: Session = Depends(db)) -> dict:
    return found(_run(s, run_id), "No such run.")


@router.get("/{run_id}/logs")
def get_logs(run_id: UUID, after: int = Query(0, ge=0), limit: int = Query(1000, ge=1, le=5000),
             who: Principal = Depends(VIEW), s: Session = Depends(db)) -> list[dict]:
    found(scalar(s, "SELECT 1 FROM collect_runs WHERE id = :r", r=str(run_id)), "No such run.")
    return rows(s, """SELECT id, at, level, message, data FROM collect_run_logs
                      WHERE run_id = :r AND id > :after ORDER BY id LIMIT :limit""",
                r=str(run_id), after=after, limit=limit)


def _snapshot(workspace_id: str, run_id: str, after: int) -> tuple[dict | None, list[dict]]:
    with tenant(workspace_id) as s:
        run = _run(s, run_id)
        logs = rows(s, """SELECT id, at, level, message, data FROM collect_run_logs
                          WHERE run_id = :r AND id > :after ORDER BY id LIMIT 500""", r=run_id, after=after)
    return run, logs


def _event(name: str, data: object, event_id: int | None = None) -> str:
    head = f"id: {event_id}\n" if event_id is not None else ""
    return f"{head}event: {name}\ndata: {json.dumps(data, default=str)}\n\n"


@router.get("/{run_id}/events")
async def stream(run_id: UUID, request: Request, after: int = Query(0, ge=0),
                 who: Principal = Depends(VIEW)) -> StreamingResponse:
    """Server-sent events: `run` when the run changes, `log` for each new line, then `end`.

    A reconnecting browser sends Last-Event-ID, so it resumes after the last line it saw.
    """
    resume = request.headers.get("last-event-id", "")
    last = int(resume) if resume.isdigit() else after
    run, _ = await run_in_threadpool(_snapshot, who.workspace_id, str(run_id), 0)
    if run is None:
        raise HTTPException(404, "No such run.")

    async def events():
        nonlocal last
        sent: str | None = None
        quiet = 0.0
        yield "retry: 2000\n\n"
        while not await request.is_disconnected():
            current, logs = await run_in_threadpool(_snapshot, who.workspace_id, str(run_id), last)
            if current is None:
                yield _event("end", {"reason": "deleted"})
                return
            changed = bool(logs)
            for line in logs:
                last = line["id"]
                yield _event("log", line, last)
            state = json.dumps(current, default=str, sort_keys=True)
            if state != sent:
                sent, changed = state, True
                yield _event("run", current)
            if current["status"] in FINISHED and len(logs) < 500:
                yield _event("end", {"status": current["status"]})
                return
            quiet = 0.0 if changed else quiet + STREAM_POLL_SECONDS
            if quiet >= STREAM_HEARTBEAT_SECONDS:
                quiet = 0.0
                yield ": keep-alive\n\n"
            await asyncio.sleep(STREAM_POLL_SECONDS)

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})


@router.post("/{run_id}/cancel")
def cancel(run_id: UUID, who: Principal = Depends(MANAGE), s: Session = Depends(db)) -> dict:
    status = cancel_run(s, str(run_id))
    if status is None:
        raise HTTPException(404, "No such run.")
    if status in FINISHED and status != "cancelled":
        raise HTTPException(409, "This run has already finished.")
    audit.record(s, who.workspace_id, who.user_id, "connection.run_cancelled", "collect_run", run_id)
    return found(_run(s, run_id), "No such run.")


@router.post("/{run_id}/retry", status_code=201)
def retry(run_id: UUID, who: Principal = Depends(MANAGE), s: Session = Depends(db)) -> dict:
    old = found(row(s, "SELECT connection_id, status FROM collect_runs WHERE id = :r", r=str(run_id)), "No such run.")
    if old["status"] not in FINISHED:
        raise HTTPException(409, "This run has not finished yet.")
    new_id = start_run(s, who.workspace_id, str(old["connection_id"]), trigger="retry", user_id=who.user_id)
    if new_id is None:
        raise HTTPException(409, "Nexus is already reading this connection.")
    audit.record(s, who.workspace_id, who.user_id, "connection.collect_requested", "connection",
                 old["connection_id"], run_id=new_id, retry_of=str(run_id))
    return {"run_id": new_id}
