"""Checking an agent's citations against the matter's passages."""

from dataclasses import dataclass, field

from nexus import search as search_index
from nexus.agents.base import UUID_RE, Agent, location
from nexus.guardrails.citations import verify_quote
from nexus.ingest.extract import PAGED

CITATION_SCHEMA = {
    "type": "object",
    "properties": {
        "passage_id": {"type": "string", "description": "The passage_id the quote comes from."},
        "quote": {
            "type": "string",
            "description": "The exact words from that passage that support the statement, copied "
                           "character for character (at least a full phrase). Use … to skip words.",
        },
    },
    "required": ["passage_id", "quote"],
    "additionalProperties": False,
}


@dataclass
class CitationReport:
    checked: int = 0
    verified: int = 0
    failures: list[dict] = field(default_factory=list)


def check(agent: Agent, citations: list[dict]) -> tuple[list[dict], CitationReport]:
    """Verify citations. Returns them enriched with document/page, plus a report.

    Each returned citation has `verified` set; failures carry a `reason`.
    """
    report = CitationReport()
    ids = [c.get("passage_id", "") for c in citations if UUID_RE.match(str(c.get("passage_id", "")))]
    with agent.session() as s:
        passages = {str(p["id"]): p for p in search_index.passages_by_id(s, agent.matter_id, ids)}
    out = []
    for c in citations:
        report.checked += 1
        pid, quote = str(c.get("passage_id", "")), c.get("quote", "")
        passage = passages.get(pid)
        if passage is None:
            reason = "The cited passage does not exist in this matter."
            verified = False
        else:
            result = verify_quote(quote, passage["text"])
            verified, reason = result.ok, result.reason
        entry = {"passage_id": pid, "quote": quote, "verified": verified}
        if passage is not None:
            entry.update(document_id=str(passage["document_id"]), document=passage["filename"],
                         page=passage["page"], position=passage["seq"], heading=passage["heading"],
                         location=location(passage),
                         location_label=PAGED.get(passage.get("content_type", ""), ""))
        if verified:
            report.verified += 1
        else:
            entry["reason"] = reason
            report.failures.append(entry)
        out.append(entry)
    return out, report
