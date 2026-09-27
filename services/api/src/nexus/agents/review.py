"""Contract review: check one document against a firm playbook.

For every position in the playbook the agent records a finding: does the
contract meet the firm's standard, deviate from it, leave it out, or is it
unclear? Findings that point at contract language must quote it exactly;
the quote is checked before the finding is accepted. The agent cannot finish
until every position has a finding. Suggested replacement language is
turned into tracked changes in a Word copy of the contract.
"""

from nexus.agents.base import (
    DOCUMENTS_ARE_DATA,
    Agent,
    RunStopped,
    Tool,
    ToolError,
    ToolOutcome,
    valid_uuid,
)
from nexus.agents.cite import check
from nexus.agents.matter_tools import matter_context, matter_tools
from nexus.db import row

STATUSES = ["meets", "deviates", "missing", "unclear"]
RISKS = ["high", "medium", "low"]
STATUS_WORDS = {"meets": "meets the standard", "deviates": "deviates", "missing": "is missing",
                "unclear": "needs a lawyer's judgement"}

SYSTEM = f"""\
You are an experienced contracts lawyer's assistant reviewing one document \
against the firm's review playbook. Your work will be checked by a lawyer \
before it goes anywhere.

How to work:
- Read the whole document in order first (use `read` from position 0 until \
the end), then search for anything you need to confirm. Definitions, \
exceptions and cross-references change what clauses mean; take them into account.
- Record exactly one finding per playbook position with record_finding:
  * meets: the document satisfies the standard position.
  * deviates: the relevant clause exists but falls short of the standard, or \
hits a red flag. Say precisely how, and whether the fallback would be acceptable.
  * missing: nothing in the document addresses the position. Only use this \
after searching with several different wordings.
  * unclear: the language is ambiguous, or the answer turns on facts or law \
you cannot see. Say what the lawyer needs to decide.
- For meets, deviates and unclear, quote the operative contract words exactly \
(character for character; quotes are checked automatically) and give the \
passage_id they come from.
- For deviates and missing, propose replacement or additional contract \
language in `suggested_language`: drafted as it would appear in the \
contract, consistent with the document's defined terms and style, and no \
broader than needed to reach the standard position. For deviates, \
`suggested_language` replaces the quoted words.
- Judge risk from our client's perspective (see the client's role below): \
high = could cause material loss or unenforceability; medium = worth \
negotiating; low = tidy-up.
- The playbook is the firm's statement of its positions, including any \
statutes or cases it cites; you may rely on and cite those. Do not add \
other statements of law from memory. Where the answer turns on facts you \
cannot see (for example whether a party is an MSME) or on law the playbook \
does not settle, mark the finding unclear and say what the lawyer must decide.
- Finish with finish_review: a short summary for the lawyer (the three to \
five points that matter most, in priority order) and a draft covering note \
to the client in plain English, in a professional tone, ready for the lawyer \
to edit.

{DOCUMENTS_ARE_DATA}"""


class ReviewAgent(Agent):
    finish_tool = "finish_review"
    # Reading a long contract in order takes many steps before findings start.
    max_steps = 60

    def __init__(self, firm_id, matter_id, run_id, document_id: str, playbook: dict,
                 client_role: str, instructions: str = ""):
        super().__init__(firm_id, matter_id, run_id)
        self.document_id = valid_uuid(document_id, "document")
        self.playbook = playbook
        self.positions = {p["id"]: p for p in playbook["positions"]}
        self.client_role = client_role
        self.instructions = instructions
        self.findings: dict[str, dict] = {}
        self.checked = 0
        self.rejected = 0

    def system_prompt(self) -> str:
        return f"{SYSTEM}\n\n{matter_context(self)}"

    def first_message(self) -> str:
        with self.session() as s:
            doc = row(s, """SELECT filename, (SELECT count(*) FROM passages WHERE document_id = d.id) AS n
                            FROM documents d WHERE id = :d AND matter_id = :m""",
                      d=self.document_id, m=self.matter_id)
        if doc is None:
            raise RunStopped("That document is not in this matter.")
        positions = "\n\n".join(
            f"[{p['id']}] {p['title']} (default risk: {p['severity']})\n"
            f"Standard: {p['standard']}\nFallback: {p['fallback']}\nRed flags: {p['red_flags']}"
            for p in self.playbook["positions"]
        )
        extra = f"\n\nInstructions from the lawyer:\n{self.instructions}" if self.instructions.strip() else ""
        return (
            f"Review “{doc['filename']}” ({doc['n']} passages, positions 0 to {doc['n'] - 1}) "
            f"against the playbook “{self.playbook['name']}”.\n\n"
            f"Our client's role in this document: {self.client_role}{extra}\n\n"
            f"Playbook positions:\n\n{positions}"
        )

    def nudge(self) -> str:
        missing = [p for p in self.positions if p not in self.findings]
        if missing:
            return (f"Findings are still missing for: {', '.join(missing)}. Call record_finding for each "
                    "(one call per position), then call finish_review.")
        return "Every position has a finding. Call finish_review with the summary and the client note."

    def tools(self) -> list[Tool]:
        return [
            *[t for t in matter_tools(self, only_document=self.document_id) if t.name != "list_documents"],
            Tool(
                "record_finding",
                "Record the finding for one playbook position. Calling it again for the same position "
                "replaces the earlier finding.",
                {
                    "type": "object",
                    "properties": {
                        "position_id": {"type": "string", "enum": list(self.positions)},
                        "status": {"type": "string", "enum": STATUSES},
                        "risk": {"type": "string", "enum": RISKS},
                        "passage_id": {"type": "string",
                                       "description": "Passage the quote comes from; \"\" when status is missing."},
                        "quote": {"type": "string",
                                  "description": "Exact contract words; \"\" when status is missing."},
                        "explanation": {"type": "string",
                                        "description": "What the clause does and how it compares with the standard, in two to four sentences."},
                        "suggested_language": {"type": "string",
                                               "description": "Proposed contract wording for deviates/missing; \"\" otherwise."},
                    },
                    "required": ["position_id", "status", "risk", "passage_id", "quote",
                                 "explanation", "suggested_language"],
                },
                self._record,
            ),
            Tool(
                "finish_review",
                "Finish once every playbook position has a finding.",
                {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string", "description": "Key points for the lawyer, in priority order."},
                        "client_note": {"type": "string", "description": "Draft covering note to the client."},
                    },
                    "required": ["summary", "client_note"],
                },
                self._finish,
            ),
        ]

    def _record(self, args: dict) -> ToolOutcome:
        pid = args.get("position_id")
        if pid not in self.positions:
            raise ToolError(f"Unknown position '{pid}'. Use one of: {', '.join(self.positions)}.")
        status = args.get("status")
        finding = {
            "position_id": pid,
            "title": self.positions[pid]["title"],
            "status": status,
            "risk": args.get("risk"),
            "explanation": (args.get("explanation") or "").strip(),
            "suggested_language": (args.get("suggested_language") or "").strip(),
            "citation": None,
        }
        if status == "missing":
            if not finding["suggested_language"]:
                raise ToolError("A missing position needs suggested_language to add to the contract.")
        else:
            citations, report = check(self, [{"passage_id": args.get("passage_id", ""),
                                              "quote": args.get("quote", "")}])
            self.checked += report.checked
            if report.failures:
                self.rejected += 1
                raise ToolError(
                    f"The quote for '{pid}' could not be verified: {report.failures[0]['reason']} "
                    "Copy the words exactly from the passage."
                )
            citation = citations[0]
            if citation["document_id"] != self.document_id:
                raise ToolError("Quote from the document under review only.")
            finding["citation"] = citation
            if status == "deviates" and not finding["suggested_language"]:
                raise ToolError("A deviation needs suggested_language to replace the quoted words.")
        self.findings[pid] = finding
        where = f" (page {finding['citation']['page']})" if finding["citation"] else ""
        return ToolOutcome(
            "Recorded.",
            f"{finding['title']}: {STATUS_WORDS[status]}{where}.",
            kind="finding",
            status="warning" if status in ("deviates", "missing") and finding["risk"] == "high" else "ok",
            detail={"finding": finding},
        )

    def _finish(self, args: dict) -> ToolOutcome:
        missing = [p for p in self.positions if p not in self.findings]
        if missing:
            raise ToolError("Record a finding for every position first. Still to do: " + ", ".join(missing))
        order = {"high": 0, "medium": 1, "low": 2}
        findings = [self.findings[p] for p in self.positions]
        self.result = {
            "document_id": self.document_id,
            "playbook": {"slug": self.playbook["slug"], "name": self.playbook["name"],
                         "validated_by": self.playbook.get("validated_by"),
                         "is_starter": self.playbook.get("is_starter", False)},
            "client_role": self.client_role,
            "summary": (args.get("summary") or "").strip(),
            "client_note": (args.get("client_note") or "").strip(),
            "findings": findings,
            "issues": sorted(
                [f for f in findings if f["status"] != "meets"],
                key=lambda f: (order.get(f["risk"], 3), f["title"]),
            ),
        }
        counts = {s: sum(f["status"] == s for f in findings) for s in STATUSES}
        return ToolOutcome(
            "Review accepted.",
            f"Review complete: {counts['meets']} meet the standard, {counts['deviates']} deviate, "
            f"{counts['missing']} missing, {counts['unclear']} for the lawyer to judge.",
            kind="answer",
        )

    def guardrail_summary(self) -> dict:
        cited = sum(1 for f in self.findings.values() if f["citation"])
        return {
            "citations_checked": self.checked,
            "citations_verified": cited,
            "statements_removed": 0,
            "sent_back_to_fix": self.rejected,
            "positions_covered": len(self.findings),
            "positions_total": len(self.positions),
        }
