"""Nexus India chronology benchmark: a List of Dates and Events from a case file.

A fictional dispute file (agreement, emails, notices, a reply, and a notice
invoking arbitration) with known dated events. The real drafting pipeline
prepares the list; it is scored on:

- date recall: each expected event's date appears in the list
- order: the dates found appear in chronological order
- sourced: every source marker in the list verified word for word
"""

import hashlib
import json
import re
import time
from datetime import date

from nexus import storage, tasks
from nexus.agents.notice import date_variants
from nexus.ai.adapters import ModelRef
from nexus.bench.lab import _bench_firm
from nexus.db import row, scalar, tenant
from nexus.ingest.extract import TEXT

FILES = {
    "01 Services agreement (extract).txt": """MASTER SERVICES AGREEMENT
This Agreement is entered into at Pune on 12 January 2026 between Kaveri Logistics Private Limited (the Customer)
and Sahyadri Software Solutions LLP (the Service Provider).
Schedule 1: Milestone 1 (driver app) is due on 31 March 2026. Milestone 2 (dashboard) is due on 30 June 2026.
Clause 9.1: Any dispute shall be referred to arbitration.""",
    "02 Email - milestone delay.txt": """From: pm@kaveri.example
To: delivery@sahyadri.example
Date: 3 April 2026
Subject: Milestone 1 not delivered

Milestone 1 was due on 31 March 2026 and has not been delivered. Please confirm a date.""",
    "03 Email - reply on delay.txt": """From: delivery@sahyadri.example
To: pm@kaveri.example
Date: 6 April 2026
Subject: Re: Milestone 1 not delivered

We expect to deliver Milestone 1 by 25 April 2026.""",
    "04 Invoice.txt": """TAX INVOICE No. SS/2026/044 dated 30 April 2026
From: Sahyadri Software Solutions LLP  To: Kaveri Logistics Private Limited
Monthly fee for April 2026: INR 4,50,000 plus GST.""",
    "05 Termination notice.txt": """Kaveri Logistics Private Limited
20 May 2026
To: Sahyadri Software Solutions LLP
Notice of termination: Milestone 1 remains undelivered despite your email of 6 April 2026. We terminate the
Agreement dated 12 January 2026 for material breach with effect from 20 May 2026.""",
    "06 Reply to termination.txt": """Sahyadri Software Solutions LLP
2 June 2026
To: Kaveri Logistics Private Limited
We dispute the termination of 20 May 2026. Milestone 1 was delivered on 18 May 2026. Invoice SS/2026/044 remains
unpaid.""",
    "07 Notice invoking arbitration.txt": """Sahyadri Software Solutions LLP
15 July 2026
To: Kaveri Logistics Private Limited
Notice under section 21 of the Arbitration and Conciliation Act, 1996: disputes having arisen under the Agreement dated
12 January 2026, we invoke arbitration under clause 9.1.""",
}

EXPECTED = [
    (date(2026, 1, 12), "agreement signed"),
    (date(2026, 3, 31), "Milestone 1 due"),
    (date(2026, 4, 3), "Kaveri's email on non-delivery"),
    (date(2026, 4, 6), "Sahyadri's reply promising 25 April"),
    (date(2026, 4, 30), "invoice SS/2026/044"),
    (date(2026, 5, 18), "Sahyadri says Milestone 1 delivered"),
    (date(2026, 5, 20), "termination notice"),
    (date(2026, 6, 2), "reply disputing termination"),
    (date(2026, 7, 15), "notice invoking arbitration (s.21)"),
]

INSTRUCTIONS = (
    "Prepare a List of Dates and Events from all documents in this matter, in the form used in Indian court filings. "
    "Use a table with two columns, Date and Event, in chronological order. Include every date that matters to the "
    "dispute. Write each event in one or two neutral, factual sentences, and give every event a source."
)


def _positions(text: str, d: date) -> list[int]:
    lower = text.lower()
    return [i for v in date_variants(d) for i in [lower.find(v.lower())] if i >= 0]


def score(content: str, sources: list[dict], unverified: list[str]) -> dict:
    found = {d: min(p) for d, _ in EXPECTED if (p := _positions(content, d))}
    ordered = [d for d, _ in sorted(found.items(), key=lambda kv: kv[1])]
    return {
        "date_recall": len(found) / len(EXPECTED),
        "missed": [label for d, label in EXPECTED if d not in found],
        "in_order": ordered == sorted(ordered),
        "sources": len(sources),
        "sources_verified": sum(1 for s in sources if s.get("verified")),
        "unverified_markers": len(unverified),
        "rows": len(re.findall(r"^\|", content, re.M)),
    }


def run(model: ModelRef, progress=print) -> dict:
    firm = _bench_firm()
    started = time.monotonic()
    with tenant(firm) as s:
        matter_id = scalar(s, "INSERT INTO matters (firm_id, name, description) VALUES (:f, :n, :d) RETURNING id",
                           f=firm, n="Chronology bench: Kaveri v Sahyadri",
                           d="Dispute over a terminated software services agreement. We act for Kaveri.")
        doc_ids = []
        for name, text in FILES.items():
            data = text.encode()
            key = storage.put(firm, "documents", data, ".txt")
            doc_ids.append(scalar(
                s, """INSERT INTO documents (firm_id, matter_id, filename, content_type, size_bytes, sha256, storage_key)
                      VALUES (:f, :m, :n, :ct, :sz, :sha, :k) RETURNING id""",
                f=firm, m=matter_id, n=name, ct=TEXT, sz=len(data), sha=hashlib.sha256(data).hexdigest(), k=key))
    for doc_id in doc_ids:
        tasks.ingest_document(firm, {"document_id": str(doc_id)})
    with tenant(firm) as s:
        run_id = scalar(s, """INSERT INTO runs (firm_id, matter_id, kind, title, input)
                              VALUES (:f, :m, 'draft', 'Chronology bench', CAST(:i AS jsonb)) RETURNING id""",
                        f=firm, m=matter_id,
                        i=json.dumps({"instructions": INSTRUCTIONS, "deliverables": ["list-of-dates.md"]}))
    tasks.run_agent(firm, {"run_id": str(run_id)}, model=model)
    with tenant(firm) as s:
        run = row(s, "SELECT status, error, output, cost_usd FROM runs WHERE id = :r", r=run_id)
    result = {"benchmark": "nexus-india-chronology", "status": run["status"], "error": run["error"],
              "seconds": round(time.monotonic() - started, 1), "cost_usd": float(run["cost_usd"])}
    if run["status"] == "needs_review":
        d = run["output"]["deliverables"][0]
        result.update(score(d["content"], d["sources"], d["unverified"]))
        progress(f"  dates found {result['date_recall']:.0%}, in order: {result['in_order']}, "
                 f"sources verified {result['sources_verified']}/{result['sources']}")
    else:
        progress(f"  {run['status']}: {run['error']}")
    return result
