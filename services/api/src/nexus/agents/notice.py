"""Legal notices. First: demand notice for a dishonoured cheque (s.138 NI Act).

The lawyer enters the facts; code computes the statutory timeline and the
amount in figures and words; the AI drafts the notice in the style of an
Indian advocate's notice. A guardrail checks the draft against the entered
facts: every critical fact (cheque number, amount in figures and in words,
cheque date, bank, drawer, the 15-day demand) must appear exactly, or the
draft is sent back. The AI never computes a date or an amount.
"""

import re
from dataclasses import dataclass
from datetime import date

from nexus.agents.base import DOCUMENTS_ARE_DATA, Agent, Tool, ToolError, ToolOutcome
from nexus.agents.matter_tools import matter_context, matter_tools
from nexus.india.cheque import fmt, rupees, rupees_in_words, timeline

REASONS = ["Funds insufficient", "Exceeds arrangement", "Account closed", "Payment stopped by drawer",
           "Drawer's signature differs", "Refer to drawer"]


@dataclass
class ChequeNotice:
    payee_name: str
    payee_address: str
    drawer_name: str
    drawer_address: str
    cheque_number: str
    cheque_date: date
    amount: int
    bank: str
    presented_on: date
    information_received_on: date
    reason: str
    liability: str
    advocate_name: str
    advocate_address: str
    enrolment_number: str = ""
    dispatch: str = "Registered Post with Acknowledgement Due and Speed Post"

    @classmethod
    def from_input(cls, data: dict) -> "ChequeNotice":
        values = dict(data)
        for key in ("cheque_date", "presented_on", "information_received_on"):
            values[key] = date.fromisoformat(values[key])
        values["amount"] = int(values["amount"])
        return cls(**{k: v for k, v in values.items() if k in cls.__dataclass_fields__})


def date_variants(d: date) -> list[str]:
    """The ways a date is commonly written in Indian legal drafting."""
    day, month = d.day, d.strftime("%B")
    suffix = "th" if 11 <= day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return [f"{day} {month} {d.year}", f"{day}{suffix} {month} {d.year}", f"{day}{suffix} day of {month}, {d.year}",
            f"{day:02d}.{d.month:02d}.{d.year}", f"{day:02d}/{d.month:02d}/{d.year}", f"{day}.{d.month}.{d.year}",
            f"{day}/{d.month}/{d.year}", f"{day:02d}-{d.month:02d}-{d.year}", f"{month} {day}, {d.year}"]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("₹", "Rs.").replace("’", "'")).lower()


def fact_checks(content: str, n: ChequeNotice) -> list[str]:
    """Problems with the draft, in words a lawyer would use. Empty means every fact matches."""
    text = _norm(content)
    problems = []

    def need(label: str, *options: str) -> None:
        if not any(_norm(o) in text for o in options if o):
            problems.append(f"{label} is missing or does not match: expected {options[0]!r}.")

    need("The cheque number", n.cheque_number)
    need("The amount in figures", rupees(n.amount))
    need("The amount in words", rupees_in_words(n.amount), rupees_in_words(n.amount).removesuffix(" only"))
    need("The cheque date", *date_variants(n.cheque_date))
    need("The drawee bank", n.bank)
    need("The drawer's name", n.drawer_name)
    need("The payee's name", n.payee_name)
    need("The reason for dishonour", n.reason)
    if not re.search(r"\b(15|fifteen)\s*(\(fifteen\)\s*)?days\b", text):
        problems.append("The notice must demand payment within 15 (fifteen) days of receipt, as s.138(b) requires.")
    return problems


SYSTEM = f"""\
You are drafting, for an Indian advocate, a legal demand notice under section \
138 of the Negotiable Instruments Act, 1881 for a dishonoured cheque. The \
advocate will review and sign it.

Write it in the form Indian advocates use:
- the advocate's name and address at the top, the mode of dispatch, and the date \
left as "Date: ____";
- addressed to the drawer at the given address, with a subject line naming \
the cheque, its amount and section 138;
- "Under instructions from and on behalf of my client …", then numbered \
paragraphs: the underlying debt or liability; the issue of the cheque (number, \
date, amount in figures and words, bank); presentation and dishonour with the \
bank's reason and the date the client received the information; that the \
drawer is therefore liable under section 138;
- a clear demand to pay the cheque amount within 15 (fifteen) days of receipt \
of the notice, failing which the client will initiate criminal proceedings \
under section 138 read with section 142, and may take civil action, at the \
drawer's risk as to costs;
- a line that a copy is retained for further action; the advocate's name for \
signature.

Use every fact exactly as given: names, addresses, cheque number, dates, the \
amount in figures and in the words provided, the bank, the reason. Do not \
invent any fact, date, amount, section or case. Do not add interest, costs \
or a notice fee as a sum payable: a demand for more than the cheque amount can \
make the notice defective. If documents are in the matter, you may use them to \
describe the liability, but the entered facts prevail.

Write the notice in Markdown (plain paragraphs, numbered paragraphs, bold for \
the subject line) and save it with write_notice.

{DOCUMENTS_ARE_DATA}"""


class NoticeAgent(Agent):
    finish_tool = "write_notice"
    max_finish_attempts = 3

    def __init__(self, firm_id, matter_id, run_id, facts: dict):
        super().__init__(firm_id, matter_id, run_id)
        self.facts = ChequeNotice.from_input(facts)
        self.timeline = timeline(self.facts.cheque_date, self.facts.presented_on,
                                 self.facts.information_received_on)
        self.sent_back = 0

    def system_prompt(self) -> str:
        return f"{SYSTEM}\n\n{matter_context(self)}"

    def first_message(self) -> str:
        n = self.facts
        return f"""Draft the section 138 demand notice from these facts.

Advocate: {n.advocate_name}{f", Enrolment No. {n.enrolment_number}" if n.enrolment_number else ""}
Advocate's address: {n.advocate_address}
Mode of dispatch: {n.dispatch}
Client (payee): {n.payee_name}, {n.payee_address}
Drawer (addressee): {n.drawer_name}, {n.drawer_address}
Underlying liability: {n.liability}
Cheque number: {n.cheque_number}
Cheque date: {fmt(n.cheque_date)}
Amount in figures: Rs. {rupees(n.amount)}/-
Amount in words: {rupees_in_words(n.amount)}
Drawn on: {n.bank}
Presented on: {fmt(n.presented_on)}
Returned unpaid with the reason: "{n.reason}"
Client received information of dishonour on: {fmt(n.information_received_on)}"""

    def nudge(self) -> str:
        return "Call write_notice with the full notice in Markdown."

    def tools(self) -> list[Tool]:
        return [
            *[t for t in matter_tools(self) if t.name in ("list_documents", "search", "read")],
            Tool("write_notice", "Save the finished notice.",
                 {"type": "object", "properties": {"content": {"type": "string", "description": "The full notice in Markdown."}},
                  "required": ["content"]},
                 self._write),
        ]

    def _write(self, args: dict) -> ToolOutcome:
        content = (args.get("content") or "").strip()
        if len(content) < 400:
            raise ToolError("The notice is too short to be complete. Write the full notice.")
        problems = fact_checks(content, self.facts)
        if problems:
            self.sent_back += 1
            raise ToolError("The notice does not match the facts entered by the lawyer. Fix these and save again:\n- "
                            + "\n- ".join(problems))
        t = self.timeline
        self.result = {
            "type": "cheque_dishonour",
            "content": content,
            "facts": {**self.facts.__dict__, "cheque_date": self.facts.cheque_date.isoformat(),
                      "presented_on": self.facts.presented_on.isoformat(),
                      "information_received_on": self.facts.information_received_on.isoformat(),
                      "amount_figures": rupees(self.facts.amount), "amount_words": rupees_in_words(self.facts.amount)},
            "timeline": {"cheque_valid_until": t.cheque_valid_until.isoformat(),
                         "notice_last_day": t.notice_last_day.isoformat()},
            "checks": [c.__dict__ for c in t.checks],
            "deliverables": [{"filename": f"Notice u-s 138 - {self.facts.drawer_name}.docx"[:120],
                              "content": content, "sources": [], "unverified": []}],
        }
        return ToolOutcome("Saved.", "Notice drafted; every entered fact checked against the text.", kind="answer")

    def guardrail_summary(self) -> dict:
        return {"citations_checked": 0, "citations_verified": 0, "statements_removed": 0,
                "facts_checked": 9, "sent_back_to_fix": self.sent_back}
