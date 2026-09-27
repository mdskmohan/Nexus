"""What the worker does: process uploaded documents and run AI tasks."""

import json
import logging

from sqlalchemy import text

from nexus import audit, deliverables, jobs, redline, storage
from nexus.agents.ask import AskAgent
from nexus.agents.base import RunStopped
from nexus.agents.draft import DraftAgent
from nexus.agents.review import ReviewAgent
from nexus.ai import registry
from nexus.ai.adapters import ModelRef, ModelUnavailable
from nexus.db import row, scalar, tenant
from nexus.guardrails.scan import scan
from nexus.ingest.chunk import chunk
from nexus.ingest.extract import DOCX, UnreadableFile, UnsupportedFile, extract
from nexus.observability import RunRecorder

log = logging.getLogger("nexus.tasks")


def ingest_document(firm_id: str, payload: dict) -> None:
    document_id = payload["document_id"]
    with tenant(firm_id) as s:
        doc = row(s, "SELECT * FROM documents WHERE id = :d", d=document_id)
        if doc is None:
            return
        scalar(s, "UPDATE documents SET status = 'processing', error = NULL WHERE id = :d RETURNING 1",
               d=document_id)
    try:
        pages = extract(storage.get(doc["storage_key"]), doc["content_type"])
        passages = chunk(pages)
        if not passages:
            raise UnreadableFile("No readable text was found in this file.")
    except (UnreadableFile, UnsupportedFile) as exc:
        with tenant(firm_id) as s:
            scalar(s, "UPDATE documents SET status = 'failed', error = :e WHERE id = :d RETURNING 1",
                   e=str(exc), d=document_id)
        return

    findings = scan([(p.seq, p.page, p.text) for p in passages])
    with tenant(firm_id) as s:
        s.execute(
            text(
                """INSERT INTO passages (firm_id, matter_id, document_id, seq, page, heading, text)
                   VALUES (:firm, :matter, :doc, :seq, :page, :heading, :text)"""
            ),
            [
                {"firm": firm_id, "matter": str(doc["matter_id"]), "doc": document_id,
                 "seq": p.seq, "page": p.page, "heading": p.heading[:300], "text": p.text}
                for p in passages
            ],
        )
        scalar(
            s,
            """UPDATE documents SET status = 'ready', page_count = :pages,
                      flags = CAST(:flags AS jsonb) WHERE id = :d RETURNING 1""",
            pages=len(pages), flags=json.dumps(findings.as_flags()), d=document_id,
        )
        audit.record(s, firm_id, None, "document.processed", "document", document_id,
                     passages=len(passages), pages=len(pages),
                     hidden_instructions=len(findings.hidden_instructions),
                     sensitive=findings.sensitive)


def run_agent(firm_id: str, payload: dict, model: ModelRef | None = None) -> None:
    """`model` overrides the run's chosen model (used by the benchmark runners)."""
    run_id = payload["run_id"]
    with tenant(firm_id) as s:
        run = row(s, "SELECT * FROM runs WHERE id = :r", r=run_id)
    if run is None or run["status"] != "queued":
        return
    recorder = RunRecorder(firm_id, run_id)
    recorder.start()
    try:
        agent = _build_agent(firm_id, run)
        agent.recorder = recorder
        agent.model = model or registry.resolve(firm_id, str(run["ai_model_id"]) if run["ai_model_id"] else None)
        result = agent.run()
        if run["kind"] == "review":
            result["files"] = _review_files(firm_id, run, result)
        elif run["kind"] == "draft":
            result["files"] = _draft_files(firm_id, run, result)
        recorder.finish(result, agent.guardrail_summary())
        with tenant(firm_id) as s:
            audit.record(s, firm_id, run["created_by"], "run.completed", "run", run_id,
                         kind=run["kind"], cost_usd=round(recorder.usage.cost_usd, 4))
    except ModelUnavailable as exc:
        log.error("run %s: %s", run_id, exc.technical)
        recorder.step("error", str(exc), status="error", error=exc.technical)
        recorder.fail(str(exc))
    except RunStopped as exc:
        recorder.step("error", str(exc), status="error")
        recorder.fail(str(exc))
    except Exception as exc:
        log.exception("run %s failed", run_id)
        recorder.step("error", "Something went wrong on our side. The task was stopped.", status="error",
                      error=f"{exc.__class__.__name__}: {exc}")
        recorder.fail("Something went wrong on our side. Please try again; if it keeps happening, "
                      "contact support with the task id.")


def _build_agent(firm_id: str, run: dict):
    data = run["input"]
    if run["kind"] == "ask":
        return AskAgent(firm_id, run["matter_id"], run["id"], data["question"])
    if run["kind"] == "draft":
        return DraftAgent(firm_id, run["matter_id"], run["id"], data["instructions"], data["deliverables"])
    if run["kind"] == "review":
        with tenant(firm_id) as s:
            playbook = row(s, "SELECT * FROM playbooks WHERE id = :p", p=data["playbook_id"])
        if playbook is None:
            raise RunStopped("The playbook for this review no longer exists.")
        return ReviewAgent(firm_id, run["matter_id"], run["id"], data["document_id"], playbook,
                           data.get("client_role", ""), data.get("instructions", ""))
    raise RuntimeError(f"unknown run kind {run['kind']!r}")


def _save_files(firm_id: str, run_id: str, files: list[tuple[str, bytes, str]]) -> list[dict]:
    out = []
    with tenant(firm_id) as s:
        for name, data, content_type in files:
            suffix = "." + name.rsplit(".", 1)[-1] if "." in name else ""
            key = storage.put(firm_id, "artifacts", data, suffix)
            artifact_id = scalar(
                s,
                """INSERT INTO artifacts (firm_id, run_id, filename, content_type, storage_key)
                   VALUES (:f, :r, :n, :ct, :k) RETURNING id""",
                f=firm_id, r=run_id, n=name, ct=content_type, k=key,
            )
            out.append({"id": str(artifact_id), "filename": name})
    return out


def _draft_files(firm_id: str, run: dict, result: dict) -> list[dict]:
    files = []
    for d in result["deliverables"]:
        data, content_type = deliverables.render(d["filename"], d["content"], d["sources"])
        files.append((d["filename"], data, content_type))
    return _save_files(firm_id, str(run["id"]), files)


def _review_files(firm_id: str, run: dict, result: dict) -> list[dict]:
    with tenant(firm_id) as s:
        doc = row(s, "SELECT filename, content_type, storage_key FROM documents WHERE id = :d",
                  d=result["document_id"])
        matter = row(s, "SELECT name FROM matters WHERE id = :m", m=run["matter_id"])
    stem = doc["filename"].rsplit(".", 1)[0]
    files = [(f"{stem} - review memo.docx",
              redline.review_memo(result, matter["name"], doc["filename"],
                                  "Check every finding against the contract before relying on it."))]
    placement = None
    if doc["content_type"] == DOCX:
        data, placement = redline.tracked_changes(storage.get(doc["storage_key"]), result["findings"])
        files.append((f"{stem} - suggested changes.docx", data))
    out = _save_files(firm_id, str(run["id"]), [(n, d, DOCX) for n, d in files])
    if placement and placement["not_placed"]:
        result["redline_not_placed"] = placement["not_placed"]
    return out


HANDLERS = {"ingest_document": ingest_document, "run_agent": run_agent}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    log.info("worker started")
    jobs.work(HANDLERS)

