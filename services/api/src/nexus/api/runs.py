"""Runs, and the requests runs make to people (approvals and questions)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from nexus.api.deps import Principal, db, found, require
from nexus.db import row, rows
from nexus.runtime import engine
from nexus.security import can

router = APIRouter(prefix="/api", tags=["runs"])

_RUN_COLUMNS = """r.id, r.kind, r.status, r.title, r.error, r.model, r.provider, r.input_tokens, r.output_tokens,
                  r.cache_read_tokens, r.cost_usd, r.created_at, r.started_at, r.finished_at,
                  u.name AS created_by_name"""


class NewRun(BaseModel):
    kind: str
    title: str = Field(min_length=1, max_length=300)
    input: dict = Field(default_factory=dict)
    ai_model_id: UUID | None = None


class DecisionIn(BaseModel):
    decision: str
    answer: str | None = Field(default=None, max_length=10_000)
    note: str | None = Field(default=None, max_length=2_000)


@router.post("/runs", status_code=201)
def start_run(body: NewRun, who: Principal = Depends(require("run_agents")), s: Session = Depends(db)) -> dict:
    if body.kind not in engine.kinds():
        raise HTTPException(422, "Unknown kind of run.")
    model_id = str(body.ai_model_id) if body.ai_model_id else None
    if model_id:
        found(row(s, "SELECT id FROM ai_models WHERE id = :m AND enabled", m=model_id), "No such AI model.")
    run_id = engine.start(s, who.workspace_id, who.user_id, body.kind, body.title.strip(), body.input, model_id)
    return {"id": run_id}


@router.get("/runs")
def list_runs(who: Principal = Depends(require("run_agents")), s: Session = Depends(db)) -> list[dict]:
    return rows(s, f"""SELECT {_RUN_COLUMNS} FROM runs r LEFT JOIN users u ON u.id = r.created_by
                       ORDER BY r.created_at DESC LIMIT 200""")


@router.get("/runs/{run_id}")
def get_run(run_id: UUID, who: Principal = Depends(require("run_agents")), s: Session = Depends(db)) -> dict:
    run = found(row(s, f"""SELECT {_RUN_COLUMNS}, r.input, r.output FROM runs r
                           LEFT JOIN users u ON u.id = r.created_by WHERE r.id = :r""", r=run_id), "No such run.")
    run["steps"] = rows(s, """SELECT seq, kind, title, status, detail, duration_ms, created_at FROM run_steps
                              WHERE run_id = :r ORDER BY seq""", r=run_id)
    run["requests"] = rows(s, """SELECT q.id, q.kind, q.title, q.shown, q.permission, q.status, q.answer, q.note,
                                        q.decided_at, q.created_at, u.name AS decided_by_name
                                 FROM human_requests q LEFT JOIN users u ON u.id = q.decided_by
                                 WHERE q.run_id = :r ORDER BY q.created_at""", r=run_id)
    return run


@router.post("/runs/{run_id}/cancel")
def cancel_run(run_id: UUID, who: Principal = Depends(require("run_agents")), s: Session = Depends(db)) -> dict:
    run = found(row(s, "SELECT created_by FROM runs WHERE id = :r", r=run_id), "No such run.")
    if str(run["created_by"]) != who.user_id and not can(who.role, "approve_runs"):
        raise HTTPException(403, "Only the person who started this run, or someone who approves runs, can stop it.")
    try:
        engine.cancel(s, who.workspace_id, who.user_id, who.name, str(run_id))
    except engine.DecisionError as exc:
        raise HTTPException(exc.status, str(exc)) from None
    return {"ok": True}


@router.get("/requests")
def open_requests(who: Principal = Depends(require("use_apps")), s: Session = Depends(db)) -> list[dict]:
    """Requests waiting for a decision that this person is allowed to make."""
    waiting = rows(s, """SELECT q.id, q.run_id, q.kind, q.title, q.shown, q.permission, q.created_at,
                                r.title AS run_title, u.name AS requested_for_name
                         FROM human_requests q JOIN runs r ON r.id = q.run_id
                         LEFT JOIN users u ON u.id = r.created_by
                         WHERE q.status = 'open' ORDER BY q.created_at""")
    return [q for q in waiting if can(who.role, q["permission"])]


@router.post("/requests/{request_id}/decide")
def decide(request_id: UUID, body: DecisionIn, who: Principal = Depends(require("use_apps")),
           s: Session = Depends(db)) -> dict:
    try:
        engine.decide(s, who.workspace_id, who.user_id, who.role, str(request_id), body.decision,
                      body.answer, body.note)
    except engine.DecisionError as exc:
        raise HTTPException(exc.status, str(exc)) from None
    return {"ok": True}
