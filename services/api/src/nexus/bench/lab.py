"""Harvey LAB (Legal Agent Benchmark) adapter.

LAB (github.com/harveyai/harvey-labs, MIT) gives an agent a matter file and
instructions; the agent writes deliverables; an LLM judge grades them
against expert rubric criteria, all-pass per task.

This adapter runs the real Nexus pipeline on a LAB task — the same ingestion,
guardrails and drafting agent a law firm uses — and writes the deliverables
into LAB's results layout, so LAB's own evaluator (unchanged) grades them:

    <lab-root>/results/<run-id>/output/<deliverable files>
    <lab-root>/results/<run-id>/metrics.json

Everything runs inside a dedicated "Benchmarks" firm, isolated from real
firms by the same row-level security as any tenant.
"""

import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from nexus import storage, tasks
from nexus.config import settings
from nexus.db import row, rows, scalar, tenant
from nexus.ingest.extract import SUPPORTED, UnsupportedFile, content_type_for

BENCH_FIRM = UUID("00000000-0000-4000-8000-00000000b3c4")


def _bench_firm() -> str:
    firm = str(BENCH_FIRM)
    with tenant(firm) as s:
        if not row(s, "SELECT id FROM firms WHERE id = :f", f=firm):
            scalar(s, "INSERT INTO firms (id, name) VALUES (:f, 'Benchmarks') RETURNING id", f=firm)
    return firm


def load_task(lab_root: Path, task_id: str) -> tuple[dict, Path]:
    task_dir = lab_root / "tasks" / task_id
    return json.loads((task_dir / "task.json").read_text()), task_dir


def list_tasks(lab_root: Path) -> list[str]:
    base = lab_root / "tasks"
    return sorted(str(p.parent.relative_to(base)) for p in base.rglob("task.json"))


def run_task(lab_root: Path, task_id: str, max_docs: int, progress=print) -> dict:
    task, task_dir = load_task(lab_root, task_id)
    docs = sorted(p for p in (task_dir / "documents").rglob("*") if p.is_file())
    supported = []
    for p in docs:
        try:
            supported.append((p, content_type_for(p.name, None)))
        except UnsupportedFile:
            continue
    if len(supported) > max_docs:
        return {"task": task_id, "skipped": f"{len(supported)} documents (limit {max_docs})"}

    firm = _bench_firm()
    started = time.monotonic()
    with tenant(firm) as s:
        matter_id = scalar(
            s, "INSERT INTO matters (firm_id, name, description) VALUES (:f, :n, :d) RETURNING id",
            f=firm, n=f"LAB: {task.get('title', task_id)}"[:200], d=f"Harvey LAB task {task_id}",
        )
        doc_ids = []
        for path, content_type in supported:
            data = path.read_bytes()
            rel = str(path.relative_to(task_dir / "documents"))
            key = storage.put(firm, "documents", data, SUPPORTED[content_type])
            doc_ids.append(scalar(
                s, """INSERT INTO documents (firm_id, matter_id, filename, content_type, size_bytes, sha256, storage_key)
                      VALUES (:f, :m, :n, :ct, :sz, :sha, :k) RETURNING id""",
                f=firm, m=matter_id, n=rel, ct=content_type, sz=len(data),
                sha=hashlib.sha256(data).hexdigest(), k=key,
            ))
    for doc_id in doc_ids:
        tasks.ingest_document(firm, {"document_id": str(doc_id)})
    with tenant(firm) as s:
        failed = rows(s, "SELECT filename, error FROM documents WHERE matter_id = :m AND status = 'failed'",
                      m=matter_id)
    progress(f"  ingested {len(doc_ids) - len(failed)}/{len(doc_ids)} documents"
             + (f" ({len(docs) - len(supported)} unsupported files skipped)" if len(docs) > len(supported) else ""))

    names = list((task.get("deliverables") or {"output.md": "output.md"}).keys())
    with tenant(firm) as s:
        run_id = scalar(
            s, """INSERT INTO runs (firm_id, matter_id, kind, title, input)
                  VALUES (:f, :m, 'draft', :t, CAST(:i AS jsonb)) RETURNING id""",
            f=firm, m=matter_id, t=f"LAB {task_id}"[:200],
            i=json.dumps({"instructions": task["instructions"], "deliverables": names}),
        )
    tasks.run_agent(firm, {"run_id": str(run_id)})

    with tenant(firm) as s:
        run = row(s, "SELECT * FROM runs WHERE id = :r", r=run_id)
        files = rows(s, "SELECT filename, storage_key FROM artifacts WHERE run_id = :r", r=run_id)
        steps = rows(s, "SELECT kind, count(*) AS n FROM run_steps WHERE run_id = :r GROUP BY kind", r=run_id)

    lab_run_id = f"{task_id}/nexus-{run['model'] or settings().model}/{datetime.now(UTC):%Y%m%d-%H%M%S}"
    out_dir = lab_root / "results" / lab_run_id / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in files:
        (out_dir / f["filename"]).write_bytes(storage.get(f["storage_key"]))
    metrics = {
        "agent": "nexus",
        "model": run["model"],
        "status": run["status"],
        "error": run["error"],
        "finish_reason": "finish_tool" if run["status"] == "needs_review" else "error",
        "finished_cleanly": run["status"] == "needs_review",
        "duration_seconds": round(time.monotonic() - started, 1),
        "input_tokens": run["input_tokens"],
        "output_tokens": run["output_tokens"],
        "cache_read_tokens": run["cache_read_tokens"],
        "cost_usd": float(run["cost_usd"]),
        "steps": {s["kind"]: s["n"] for s in steps},
        "guardrails": run["guardrails"],
        "documents": {"ingested": len(doc_ids) - len(failed), "failed": failed,
                      "unsupported": len(docs) - len(supported)},
    }
    (out_dir.parent / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str))
    (out_dir.parent / "config.json").write_text(json.dumps(
        {"task": task_id, "agent": "nexus", "model": run["model"], "effort": settings().effort}, indent=2))
    return {"task": task_id, "run_id": lab_run_id, **{k: metrics[k] for k in
            ("status", "error", "cost_usd", "duration_seconds")}, "files": [f["filename"] for f in files]}
