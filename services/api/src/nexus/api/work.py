"""AI task results and sign-off, playbooks, firm settings, and activity."""

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from nexus import audit, storage
from nexus.api.auth import seed_playbooks
from nexus.api.deps import Principal, attachment, db, found, principal, require
from nexus.config import settings
from nexus.db import row, rows, scalar
from nexus.observability import firm_metrics

router = APIRouter(prefix="/api", tags=["work"])

_RUN_COLUMNS = """r.id, r.matter_id, r.kind, r.status, r.title, r.created_at, r.started_at, r.finished_at,
                  r.cost_usd, r.guardrails, u.name AS created_by_name, rv.name AS reviewed_by_name,
                  r.reviewed_at"""


class Decision(BaseModel):
    note: str = Field(default="", max_length=4000)


class PlaybookUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    positions: list[dict]


class Validation(BaseModel):
    lawyer_name: str = Field(min_length=2, max_length=200)


class FirmUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    preferences: str | None = Field(default=None, max_length=8000)


# Runs ---------------------------------------------------------------------

@router.get("/matters/{matter_id}/runs")
def matter_runs(matter_id: UUID, s: Session = Depends(db)) -> list[dict]:
    return rows(
        s,
        f"""SELECT {_RUN_COLUMNS} FROM runs r
            LEFT JOIN users u ON u.id = r.created_by LEFT JOIN users rv ON rv.id = r.reviewed_by
            WHERE r.matter_id = :m ORDER BY r.created_at DESC""",
        m=matter_id,
    )


@router.get("/runs/{run_id}")
def get_run(run_id: UUID, s: Session = Depends(db)) -> dict:
    run = found(row(
        s,
        f"""SELECT {_RUN_COLUMNS}, r.input, r.output, r.error, r.review_note, r.model,
                   r.input_tokens, r.output_tokens, r.cache_read_tokens, r.provider, m.name AS matter_name
            FROM runs r JOIN matters m ON m.id = r.matter_id
            LEFT JOIN users u ON u.id = r.created_by LEFT JOIN users rv ON rv.id = r.reviewed_by
            WHERE r.id = :r""",
        r=run_id,
    ), "No such task.")
    run["steps"] = rows(
        s, "SELECT seq, kind, title, status, detail, duration_ms, created_at FROM run_steps WHERE run_id = :r ORDER BY seq",
        r=run_id,
    )
    run["files"] = rows(s, "SELECT id, filename, created_at FROM artifacts WHERE run_id = :r ORDER BY created_at",
                        r=run_id)
    return run


def _decide(s: Session, who: Principal, run_id: UUID, status: str, note: str) -> dict:
    current = found(row(s, "SELECT status FROM runs WHERE id = :r", r=run_id), "No such task.")
    if current["status"] not in ("needs_review", "approved", "rejected"):
        raise HTTPException(409, "Only a finished task can be approved or sent back.")
    scalar(
        s,
        """UPDATE runs SET status = :st, reviewed_by = :u, reviewed_at = now(), review_note = :n
           WHERE id = :r RETURNING id""",
        st=status, u=who.user_id, n=note.strip() or None, r=run_id,
    )
    audit.record(s, who.firm_id, who.user_id, f"run.{status}", "run", run_id, note=note.strip())
    return {"ok": True}


@router.post("/runs/{run_id}/approve")
def approve(run_id: UUID, body: Decision, who: Principal = Depends(require("associate")),
            s: Session = Depends(db)) -> dict:
    return _decide(s, who, run_id, "approved", body.note)


@router.post("/runs/{run_id}/reject")
def reject(run_id: UUID, body: Decision, who: Principal = Depends(require("associate")),
           s: Session = Depends(db)) -> dict:
    return _decide(s, who, run_id, "rejected", body.note)


@router.post("/runs/{run_id}/cancel")
def cancel(run_id: UUID, who: Principal = Depends(principal), s: Session = Depends(db)) -> dict:
    stopped = scalar(
        s, """UPDATE runs SET status = 'cancelled', finished_at = now(), error = :e
              WHERE id = :r AND status IN ('queued', 'running') RETURNING id""",
        r=run_id, e=f"Stopped by {who.name}.",
    )
    if stopped is None:
        found(row(s, "SELECT id FROM runs WHERE id = :r", r=run_id), "No such task.")
        raise HTTPException(409, "This task has already finished.")
    audit.record(s, who.firm_id, who.user_id, "run.cancelled", "run", run_id)
    return {"ok": True}


@router.get("/files/{file_id}")
def download_file(file_id: UUID, who: Principal = Depends(principal), s: Session = Depends(db)) -> Response:
    f = found(row(s, "SELECT filename, content_type, storage_key, run_id FROM artifacts WHERE id = :a",
                  a=file_id), "No such file.")
    audit.record(s, who.firm_id, who.user_id, "file.downloaded", "file", file_id, run_id=str(f["run_id"]))
    return Response(storage.get(f["storage_key"]), media_type=f["content_type"],
                    headers=attachment(f["filename"]))


# Playbooks ----------------------------------------------------------------

@router.get("/playbooks")
def list_playbooks(who: Principal = Depends(principal), s: Session = Depends(db)) -> list[dict]:
    seed_playbooks(s, who.firm_id)  # new starters reach existing firms; existing ones are never overwritten
    return rows(s, """SELECT id, slug, name, description, document_type, is_starter, validated_by,
                             validated_at, jsonb_array_length(positions) AS position_count, updated_at
                      FROM playbooks ORDER BY is_starter, slug LIKE '%-india' DESC, name""")


@router.get("/playbooks/{playbook_id}")
def get_playbook(playbook_id: UUID, s: Session = Depends(db)) -> dict:
    return found(row(s, "SELECT * FROM playbooks WHERE id = :p", p=playbook_id), "No such playbook.")


_REQUIRED_POSITION_KEYS = {"id", "title", "standard", "fallback", "red_flags", "severity"}


@router.put("/playbooks/{playbook_id}")
def update_playbook(playbook_id: UUID, body: PlaybookUpdate, who: Principal = Depends(require("partner")),
                    s: Session = Depends(db)) -> dict:
    ids = set()
    for p in body.positions:
        missing = _REQUIRED_POSITION_KEYS - p.keys()
        if missing:
            raise HTTPException(422, f"Each position needs: {', '.join(sorted(missing))}.")
        if p["severity"] not in ("high", "medium", "low"):
            raise HTTPException(422, "Severity must be high, medium or low.")
        if p["id"] in ids:
            raise HTTPException(422, f"Duplicate position id {p['id']}.")
        ids.add(p["id"])
    # Any edit clears the approval: the approved version is no longer the one in use.
    found(scalar(
        s,
        """UPDATE playbooks SET name = :n, description = :d, positions = CAST(:pos AS jsonb),
                  validated_by = NULL, validated_at = NULL, updated_at = now()
           WHERE id = :p RETURNING id""",
        n=body.name, d=body.description, pos=json.dumps(body.positions), p=playbook_id,
    ), "No such playbook.")
    audit.record(s, who.firm_id, who.user_id, "playbook.updated", "playbook", playbook_id)
    return {"ok": True}


@router.post("/playbooks/{playbook_id}/validate")
def validate_playbook(playbook_id: UUID, body: Validation, who: Principal = Depends(require("partner")),
                      s: Session = Depends(db)) -> dict:
    found(scalar(
        s,
        """UPDATE playbooks SET validated_by = :v, validated_at = now() WHERE id = :p RETURNING id""",
        v=body.lawyer_name.strip(), p=playbook_id,
    ), "No such playbook.")
    audit.record(s, who.firm_id, who.user_id, "playbook.approved", "playbook", playbook_id,
                 lawyer=body.lawyer_name.strip())
    return {"ok": True}


# Firm ---------------------------------------------------------------------

@router.patch("/firm")
def update_firm(body: FirmUpdate, who: Principal = Depends(require("partner")),
                s: Session = Depends(db)) -> dict:
    scalar(s, """UPDATE firms SET name = coalesce(:n, name), preferences = coalesce(:p, preferences)
                 WHERE id = :f RETURNING id""", n=body.name, p=body.preferences, f=who.firm_id)
    audit.record(s, who.firm_id, who.user_id, "firm.updated", "firm", who.firm_id,
                 fields=list(body.model_dump(exclude_none=True)))
    return {"ok": True}


# Activity and safety ------------------------------------------------------

@router.get("/activity")
def activity(who: Principal = Depends(principal), s: Session = Depends(db)) -> dict:
    return {
        "metrics": firm_metrics(who.firm_id),
        "runs": rows(
            s,
            f"""SELECT {_RUN_COLUMNS}, m.name AS matter_name FROM runs r
                JOIN matters m ON m.id = r.matter_id
                LEFT JOIN users u ON u.id = r.created_by LEFT JOIN users rv ON rv.id = r.reviewed_by
                ORDER BY r.created_at DESC LIMIT 50""",
        ),
        "flagged_documents": rows(
            s,
            """SELECT d.id, d.filename, d.matter_id, m.name AS matter_name, d.flags FROM documents d
               JOIN matters m ON m.id = d.matter_id
               WHERE (d.flags->>'hidden_instruction_count')::int > 0 OR d.flags->'sensitive' <> '{}'::jsonb
               ORDER BY d.created_at DESC LIMIT 50""",
        ),
        "limits": {"max_steps": settings().agent_max_steps, "budget_usd": settings().agent_budget_usd},
    }


@router.get("/audit")
def audit_log(who: Principal = Depends(require("partner")), s: Session = Depends(db)) -> list[dict]:
    return audit.recent(s, 200)
