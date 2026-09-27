"""Nexus India contract-review benchmark.

Original Indian-law contracts with known, planted issues (nexus/samples_india.py).
For each one, the real review pipeline runs (ingestion, review agent, citation
checks) and its findings are compared with the expected result per playbook
position:

- issue recall: planted issues reported as deviates, missing or unclear
- false alarms: positions that meet the standard but were reported as issues
- citation integrity: every finding that quotes the contract has a verified quote
- completion: the review finished with a finding for every position

Expectations were written with the contracts and have not yet been validated
by a practising lawyer; results are labelled accordingly.
"""

import hashlib
import json
import time

from nexus import storage, tasks
from nexus.ai.adapters import ModelRef
from nexus.bench.lab import _bench_firm
from nexus.db import row, scalar, tenant
from nexus.ingest.extract import DOCX
from nexus.playbooks_india import INDIA
from nexus.samples_india import CASES, contract_docx

ISSUE = {"deviates", "missing", "unclear"}


def score(expected: dict[str, str], findings: list[dict]) -> dict:
    got = {f["position_id"]: f["status"] for f in findings}
    issues = [p for p, e in expected.items() if e == "issue"]  # "either" is not scored
    meets = [p for p, e in expected.items() if e == "meets"]
    caught = [p for p in issues if got.get(p) in ISSUE]
    false_alarms = [p for p in meets if got.get(p) in ISSUE]
    cited = [f for f in findings if f.get("citation")]
    return {
        "completed_positions": sum(1 for p in expected if p in got),
        "issues": len(issues), "caught": len(caught), "missed": sorted(set(issues) - set(caught)),
        "meets": len(meets), "false_alarms": false_alarms,
        "citations": len(cited), "citations_verified": sum(1 for f in cited if f["citation"].get("verified")),
    }


def run_case(case: dict, model: ModelRef, progress=print) -> dict:
    firm = _bench_firm()
    playbook_spec = next(p for p in INDIA if p["slug"] == case["playbook"])
    data = contract_docx(case["clauses"])
    started = time.monotonic()
    with tenant(firm) as s:
        playbook_id = scalar(s, "SELECT id FROM playbooks WHERE slug = :s", s=playbook_spec["slug"])
        if playbook_id is None:
            playbook_id = scalar(
                s, """INSERT INTO playbooks (firm_id, slug, name, description, document_type, positions, is_starter)
                      VALUES (:f, :slug, :n, :d, :dt, CAST(:pos AS jsonb), true) RETURNING id""",
                f=firm, slug=playbook_spec["slug"], n=playbook_spec["name"], d=playbook_spec["description"],
                dt=playbook_spec["document_type"], pos=json.dumps(playbook_spec["positions"]))
        matter_id = scalar(s, "INSERT INTO matters (firm_id, name) VALUES (:f, :n) RETURNING id",
                           f=firm, n=f"India review bench: {case['name']}")
        key = storage.put(firm, "documents", data, ".docx")
        doc_id = scalar(
            s, """INSERT INTO documents (firm_id, matter_id, filename, content_type, size_bytes, sha256, storage_key)
                  VALUES (:f, :m, :n, :ct, :sz, :sha, :k) RETURNING id""",
            f=firm, m=matter_id, n=f"{case['name']}.docx", ct=DOCX, sz=len(data),
            sha=hashlib.sha256(data).hexdigest(), k=key)
    tasks.ingest_document(firm, {"document_id": str(doc_id)})
    with tenant(firm) as s:
        run_id = scalar(
            s, """INSERT INTO runs (firm_id, matter_id, kind, title, input)
                  VALUES (:f, :m, 'review', :t, CAST(:i AS jsonb)) RETURNING id""",
            f=firm, m=matter_id, t=f"India bench {case['name']}",
            i=json.dumps({"document_id": str(doc_id), "playbook_id": str(playbook_id),
                          "client_role": case["client_role"]}))
    tasks.run_agent(firm, {"run_id": str(run_id)}, model=model)
    with tenant(firm) as s:
        run = row(s, "SELECT status, error, output, cost_usd, input_tokens, output_tokens FROM runs WHERE id = :r",
                  r=run_id)
    result = {"case": case["name"], "run_id": str(run_id), "status": run["status"], "error": run["error"],
              "seconds": round(time.monotonic() - started, 1), "cost_usd": float(run["cost_usd"]),
              "tokens": run["input_tokens"] + run["output_tokens"]}
    if run["status"] == "needs_review":
        result.update(score(case["expected"], run["output"]["findings"]))
    progress(f"  {case['name']}: {run['status']}"
             + (f", caught {result['caught']}/{result['issues']} issues, "
                f"{len(result['false_alarms'])} false alarms" if "caught" in result else f" ({run['error']})"))
    return result


def run(model: ModelRef, progress=print) -> dict:
    results = [run_case(c, model, progress) for c in CASES]
    done = [r for r in results if "caught" in r]
    issues = sum(r["issues"] for r in done)
    return {
        "benchmark": "nexus-india-contract-review",
        "validated_by_lawyer": False,
        "cases": len(results), "completed": len(done),
        "issue_recall": sum(r["caught"] for r in done) / issues if issues else None,
        "false_alarms": sum(len(r["false_alarms"]) for r in done),
        "citations_verified": f"{sum(r['citations_verified'] for r in done)}/{sum(r['citations'] for r in done)}",
        "cost_usd": round(sum(r["cost_usd"] for r in results), 4),
        "results": results,
    }
