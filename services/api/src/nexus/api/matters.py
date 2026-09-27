"""Matters, their documents, and the AI tasks run on them."""

import hashlib
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from nexus import audit, jobs, storage
from nexus.agents.draft import SAFE_NAME
from nexus.ai import registry
from nexus.api.deps import Principal, attachment, db, found, principal, require
from nexus.config import settings
from nexus.db import row, rows, scalar
from nexus.ingest.extract import SUPPORTED, UnsupportedFile, content_type_for

router = APIRouter(prefix="/api", tags=["matters"])


class NewMatter(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    client_name: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=4000)


class MatterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    client_name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    status: str | None = Field(default=None, pattern="^(open|closed)$")


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=4000)
    model_id: str | None = None


class DraftRequest(BaseModel):
    instructions: str = Field(min_length=10, max_length=20000)
    deliverables: list[str] = Field(default_factory=lambda: ["draft.docx"], min_length=1, max_length=6)
    model_id: str | None = None


class ReviewRequest(BaseModel):
    document_id: UUID
    playbook_id: UUID
    client_role: str = Field(min_length=2, max_length=500)
    instructions: str = Field(default="", max_length=4000)
    model_id: str | None = None


# Matters ------------------------------------------------------------------

@router.get("/matters")
def list_matters(s: Session = Depends(db)) -> list[dict]:
    return rows(
        s,
        """SELECT m.id, m.name, m.client_name, m.status, m.created_at,
                  (SELECT count(*) FROM documents d WHERE d.matter_id = m.id) AS documents,
                  (SELECT count(*) FROM runs r WHERE r.matter_id = m.id) AS tasks,
                  (SELECT count(*) FROM runs r WHERE r.matter_id = m.id AND r.status = 'needs_review') AS awaiting_review,
                  greatest(m.created_at, (SELECT max(created_at) FROM runs r WHERE r.matter_id = m.id)) AS last_activity
           FROM matters m ORDER BY last_activity DESC NULLS LAST""",
    )


@router.post("/matters", status_code=201)
def create_matter(body: NewMatter, who: Principal = Depends(principal), s: Session = Depends(db)) -> dict:
    matter_id = scalar(
        s,
        """INSERT INTO matters (firm_id, name, client_name, description, created_by)
           VALUES (:f, :n, :c, :d, :u) RETURNING id""",
        f=who.firm_id, n=body.name.strip(), c=body.client_name.strip(), d=body.description.strip(),
        u=who.user_id,
    )
    audit.record(s, who.firm_id, who.user_id, "matter.created", "matter", matter_id)
    return {"id": str(matter_id)}


@router.get("/matters/{matter_id}")
def get_matter(matter_id: UUID, s: Session = Depends(db)) -> dict:
    return found(row(s, "SELECT * FROM matters WHERE id = :m", m=matter_id), "No such matter.")


@router.patch("/matters/{matter_id}")
def update_matter(matter_id: UUID, body: MatterUpdate, who: Principal = Depends(principal),
                  s: Session = Depends(db)) -> dict:
    changes = body.model_dump(exclude_none=True)
    found(scalar(
        s,
        """UPDATE matters SET name = coalesce(:name, name), client_name = coalesce(:client_name, client_name),
                  description = coalesce(:description, description), status = coalesce(:status, status)
           WHERE id = :m RETURNING id""",
        m=matter_id, **{k: changes.get(k) for k in ("name", "client_name", "description", "status")},
    ), "No such matter.")
    audit.record(s, who.firm_id, who.user_id, "matter.updated", "matter", matter_id, **changes)
    return {"ok": True}


# Documents ----------------------------------------------------------------

@router.get("/matters/{matter_id}/documents")
def list_documents(matter_id: UUID, s: Session = Depends(db)) -> list[dict]:
    return rows(
        s,
        """SELECT d.id, d.filename, d.content_type, d.size_bytes, d.status, d.page_count, d.error,
                  d.flags, d.created_at, u.name AS uploaded_by
           FROM documents d LEFT JOIN users u ON u.id = d.uploaded_by
           WHERE d.matter_id = :m ORDER BY d.created_at""",
        m=matter_id,
    )


@router.post("/matters/{matter_id}/documents", status_code=201)
async def upload(matter_id: UUID, files: list[UploadFile], who: Principal = Depends(principal),
                 s: Session = Depends(db)) -> list[dict]:
    found(row(s, "SELECT id FROM matters WHERE id = :m", m=matter_id), "No such matter.")
    limit = settings().max_upload_mb * 1024 * 1024
    created = []
    for upload_file in files:
        name = upload_file.filename or "document"
        try:
            content_type = content_type_for(name, upload_file.content_type)
        except UnsupportedFile as exc:
            raise HTTPException(415, f"{name}: {exc}") from None
        data = await upload_file.read(limit + 1)
        if len(data) > limit:
            raise HTTPException(413, f"{name} is larger than {settings().max_upload_mb} MB.")
        if not data:
            raise HTTPException(422, f"{name} is empty.")
        key = storage.put(who.firm_id, "documents", data, SUPPORTED[content_type])
        doc_id = scalar(
            s,
            """INSERT INTO documents (firm_id, matter_id, filename, content_type, size_bytes, sha256,
                                      storage_key, uploaded_by)
               VALUES (:f, :m, :n, :ct, :sz, :sha, :k, :u) RETURNING id""",
            f=who.firm_id, m=matter_id, n=name, ct=content_type, sz=len(data),
            sha=hashlib.sha256(data).hexdigest(), k=key, u=who.user_id,
        )
        jobs.enqueue(s, who.firm_id, "ingest_document", {"document_id": str(doc_id)})
        audit.record(s, who.firm_id, who.user_id, "document.uploaded", "document", doc_id,
                     filename=name, matter_id=str(matter_id))
        created.append({"id": str(doc_id), "filename": name})
    return created


@router.get("/documents/{document_id}")
def get_document(document_id: UUID, s: Session = Depends(db)) -> dict:
    return found(row(
        s,
        """SELECT d.id, d.matter_id, d.filename, d.content_type, d.size_bytes, d.sha256, d.status,
                  d.page_count, d.error, d.flags, d.created_at
           FROM documents d WHERE d.id = :d""",
        d=document_id,
    ), "No such document.")


@router.get("/documents/{document_id}/passages")
def document_passages(document_id: UUID, s: Session = Depends(db)) -> list[dict]:
    return rows(s, "SELECT id, seq, page, heading, text FROM passages WHERE document_id = :d ORDER BY seq",
                d=document_id)


@router.get("/documents/{document_id}/file")
def download_document(document_id: UUID, who: Principal = Depends(principal),
                      s: Session = Depends(db)) -> Response:
    doc = found(row(s, "SELECT filename, content_type, storage_key FROM documents WHERE id = :d",
                    d=document_id), "No such document.")
    audit.record(s, who.firm_id, who.user_id, "document.downloaded", "document", document_id)
    return Response(storage.get(doc["storage_key"]), media_type=doc["content_type"],
                    headers=attachment(doc["filename"]))


@router.delete("/documents/{document_id}")
def delete_document(document_id: UUID, who: Principal = Depends(require("associate")),
                    s: Session = Depends(db)) -> dict:
    doc = found(row(s, "SELECT storage_key, filename FROM documents WHERE id = :d", d=document_id),
                "No such document.")
    scalar(s, "DELETE FROM documents WHERE id = :d RETURNING 1", d=document_id)
    storage.delete(doc["storage_key"])
    audit.record(s, who.firm_id, who.user_id, "document.deleted", "document", document_id,
                 filename=doc["filename"])
    return {"ok": True}


# AI tasks -----------------------------------------------------------------

def _start_run(s: Session, who: Principal, matter_id: UUID, kind: str, title: str, data: dict,
               model_id: str | None) -> dict:
    choosable = {m["id"] for m in registry.available(who.firm_id)}
    if not choosable:
        raise HTTPException(409, "The AI is not connected yet. Ask your administrator to add an AI model in Firm settings.")
    if model_id and model_id not in choosable:
        raise HTTPException(422, "That AI model is not available. Choose another.")
    run_id = scalar(
        s,
        """INSERT INTO runs (firm_id, matter_id, kind, title, input, created_by, ai_model_id)
           VALUES (:f, :m, :k, :t, CAST(:i AS jsonb), :u, CAST(:mid AS uuid)) RETURNING id""",
        f=who.firm_id, m=matter_id, k=kind, t=title, i=json.dumps(data), u=who.user_id,
        mid=model_id if model_id and model_id != registry.PLATFORM_ID else None,
    )
    # AI runs are not retried automatically: a retry costs money and may give a
    # different answer. The lawyer can start the task again.
    jobs.enqueue(s, who.firm_id, "run_agent", {"run_id": str(run_id)}, max_attempts=1)
    audit.record(s, who.firm_id, who.user_id, "run.started", "run", run_id, kind=kind)
    return {"id": str(run_id)}


def _ready_documents(s: Session, matter_id: UUID) -> int:
    return scalar(s, "SELECT count(*) FROM documents WHERE matter_id = :m AND status = 'ready'",
                  m=matter_id)


@router.post("/matters/{matter_id}/ask", status_code=201)
def ask(matter_id: UUID, body: Question, who: Principal = Depends(principal),
        s: Session = Depends(db)) -> dict:
    found(row(s, "SELECT id FROM matters WHERE id = :m", m=matter_id), "No such matter.")
    if not _ready_documents(s, matter_id):
        raise HTTPException(409, "Add at least one document to this matter first (and wait for it to finish processing).")
    return _start_run(s, who, matter_id, "ask", body.question.strip()[:200], {"question": body.question.strip()},
                      body.model_id)


@router.post("/matters/{matter_id}/reviews", status_code=201)
def review(matter_id: UUID, body: ReviewRequest, who: Principal = Depends(principal),
           s: Session = Depends(db)) -> dict:
    doc = found(row(s, "SELECT filename, status FROM documents WHERE id = :d AND matter_id = :m",
                    d=body.document_id, m=matter_id), "No such document in this matter.")
    if doc["status"] != "ready":
        raise HTTPException(409, "That document has not finished processing yet.")
    playbook = found(row(s, "SELECT name FROM playbooks WHERE id = :p", p=body.playbook_id),
                     "No such playbook.")
    data = {"document_id": str(body.document_id), "playbook_id": str(body.playbook_id),
            "client_role": body.client_role.strip(), "instructions": body.instructions.strip()}
    return _start_run(s, who, matter_id, "review", f"Review of {doc['filename']} — {playbook['name']}", data,
                      body.model_id)


@router.post("/matters/{matter_id}/drafts", status_code=201)
def draft(matter_id: UUID, body: DraftRequest, who: Principal = Depends(principal),
          s: Session = Depends(db)) -> dict:
    found(row(s, "SELECT id FROM matters WHERE id = :m", m=matter_id), "No such matter.")
    if not _ready_documents(s, matter_id):
        raise HTTPException(409, "Add at least one document to this matter first (and wait for it to finish processing).")
    names = [n.strip() for n in body.deliverables]
    bad = [n for n in names if not SAFE_NAME.match(n)]
    if bad:
        raise HTTPException(422, f"File names must end in .docx, .xlsx or .md and use ordinary characters: {', '.join(bad)}")
    if len(set(n.lower() for n in names)) != len(names):
        raise HTTPException(422, "Each file needs a different name.")
    title = f"Draft: {', '.join(names)}"
    return _start_run(s, who, matter_id, "draft", title,
                      {"instructions": body.instructions.strip(), "deliverables": names}, body.model_id)
