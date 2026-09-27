"""Draft work product: memos, issues lists, schedules, letters.

The agent researches the matter, then writes each requested file in Markdown
with source markers ([S1], [S2] …). Each marker names a passage and an exact
quote. Sources are verified before the file is accepted; the agent gets two
chances to fix any that fail, after which the file is accepted with the
failing markers rendered as "[unverified]" and listed for the lawyer, so
nothing unverified is ever presented as if it were sourced.
"""

import re

from nexus import deliverables
from nexus.agents.base import DOCUMENTS_ARE_DATA, Agent, Tool, ToolError, ToolOutcome
from nexus.agents.cite import check
from nexus.agents.matter_tools import matter_context, matter_tools

SAFE_NAME = re.compile(r"^[\w][\w .()&,'-]{0,120}\.(docx|xlsx|md)$", re.IGNORECASE)
MAX_FIX_ROUNDS = 2

SYSTEM = f"""\
You are a senior associate at a law firm preparing work product from the \
documents in one matter. A supervising lawyer will review your work before \
it goes anywhere.

How to work:
- Start by listing the documents, then read every document that could \
matter to the task. For large files, search with several wordings and read \
around each hit. Take definitions, exceptions, schedules, side letters, \
emails and later amendments into account: the most recent or most specific \
document often controls.
- Follow the instructions exactly: the deliverables asked for, their \
names, structure, headings, addressees, format and level of detail. If the \
instructions set out topics or questions, address every one, in order, \
under clear headings.
- Be specific and complete. Name parties, dates, amounts, section numbers, \
deadlines and thresholds. Quantify where the documents allow. Identify \
risks, inconsistencies, missing documents and open questions, and say what \
should be done about each. Give a clear bottom line.
- Support every statement of fact about the matter with a source marker \
[S1], [S2] … and list each source in `sources` with the passage_id and the \
exact words from that passage. Quotes are checked word for word; a source \
that does not match is rejected. Legal analysis and judgement need no \
source, but must not invent facts, cases or statutes. If you rely on \
general legal principles, say so and keep them at the level of generality \
a careful lawyer would stand behind.
- Where the documents do not contain something the task needs, say so in \
the deliverable rather than filling the gap.
- Write deliverables in Markdown: # headings, paragraphs, - bullets, 1. \
numbered lists, **bold**, and | pipe | tables |. For .xlsx deliverables, put \
the data in pipe tables (one table per sheet, each under a # heading naming \
the sheet).

{DOCUMENTS_ARE_DATA}

Write each deliverable with write_deliverable (calling it again for the same \
file replaces it), then call finish."""


class DraftAgent(Agent):
    finish_tool = "finish"
    max_steps = 80

    def __init__(self, firm_id, matter_id, run_id, instructions: str, deliverable_names: list[str]):
        super().__init__(firm_id, matter_id, run_id)
        self.instructions = instructions
        self.names = deliverable_names or ["draft.docx"]
        self.files: dict[str, dict] = {}
        self.fix_rounds: dict[str, int] = {}
        self.checked = 0

    def system_prompt(self) -> str:
        return f"{SYSTEM}\n\n{matter_context(self)}"

    def first_message(self) -> str:
        return (f"Task from the supervising lawyer:\n{self.instructions}\n\n"
                f"Deliverables to write: {', '.join(self.names)}")

    def nudge(self) -> str:
        missing = [n for n in self.names if n not in self.files]
        if missing:
            return (f"Nothing has been saved yet for: {', '.join(missing)}. Writing text in your reply does not "
                    f"save a file. Call write_deliverable with filename \"{missing[0]}\", the full content in "
                    "Markdown, and its sources. Then call finish.")
        return "All deliverables are written. Call finish with a short summary."

    def tools(self) -> list[Tool]:
        return [
            *matter_tools(self),
            Tool(
                "write_deliverable",
                "Write (or replace) one deliverable file.",
                {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string", "enum": self.names},
                        "content": {"type": "string", "description": "The full document in Markdown, with [S1]-style source markers."},
                        "sources": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string", "description": "Marker id without brackets, e.g. S1."},
                                    "passage_id": {"type": "string"},
                                    "quote": {"type": "string", "description": "Exact words from the passage."},
                                },
                                "required": ["id", "passage_id", "quote"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": ["filename", "content", "sources"],
                },
                self._write,
            ),
            Tool(
                "finish",
                "Finish once every deliverable has been written.",
                {
                    "type": "object",
                    "properties": {"summary": {"type": "string", "description": "Two or three sentences for the lawyer: what you produced and anything they must check."}},
                    "required": ["summary"],
                },
                self._finish,
            ),
        ]

    def _write(self, args: dict) -> ToolOutcome:
        name = args.get("filename", "")
        if name not in self.names:
            raise ToolError(f"Write only the requested deliverables: {', '.join(self.names)}.")
        content = (args.get("content") or "").strip()
        if len(content) < 20:
            raise ToolError("The deliverable is empty.")
        declared = {s.get("id", "").strip("[] "): s for s in (args.get("sources") or [])}
        used = set(deliverables.MARKER.findall(content))
        citations, report = check(self, [{"passage_id": declared[sid].get("passage_id", ""),
                                           "quote": declared[sid].get("quote", "")}
                                          for sid in sorted(used) if sid in declared])
        self.checked += report.checked
        sources = []
        for sid, c in zip([s for s in sorted(used) if s in declared], citations, strict=True):
            sources.append({"id": sid, **c})
        undeclared = sorted(used - set(declared))
        failing = [s for s in sources if not s["verified"]]
        if (failing or undeclared) and self.fix_rounds.get(name, 0) < MAX_FIX_ROUNDS:
            self.fix_rounds[name] = self.fix_rounds.get(name, 0) + 1
            problems = [f"[{s['id']}]: {s['reason']}" for s in failing]
            problems += [f"[{sid}] is used in the text but not listed in sources." for sid in undeclared]
            raise ToolError("Some sources could not be verified. Fix each (copy the quote exactly, "
                            "cite a passage that supports it, or remove the marker and the claim), "
                            "then write the file again:\n- " + "\n- ".join(problems))
        unverified = [s["id"] for s in failing] + undeclared
        self.files[name] = {"filename": name, "content": content, "sources": sources, "unverified": unverified}
        verified = len(sources) - len(failing)
        title = f"Wrote {name}: {verified} source{'s' if verified != 1 else ''} checked word for word."
        if unverified:
            title += f" {len(unverified)} marked as unverified."
        return ToolOutcome("Saved.", title, kind="answer", status="warning" if unverified else "ok",
                           detail={"unverified": unverified, "chars": len(content)})

    def _finish(self, args: dict) -> ToolOutcome:
        missing = [n for n in self.names if n not in self.files]
        if missing:
            raise ToolError("Write every deliverable before finishing. Still missing: " + ", ".join(missing))
        self.result = {"summary": (args.get("summary") or "").strip(),
                       "instructions": self.instructions,
                       "deliverables": [self.files[n] for n in self.names]}
        return ToolOutcome("Done.", f"Drafting complete: {len(self.names)} file{'s' if len(self.names) != 1 else ''}.",
                           kind="answer")

    def guardrail_summary(self) -> dict:
        files = self.files.values()
        return {
            "citations_checked": self.checked,
            "citations_verified": sum(sum(1 for s in f["sources"] if s["verified"]) for f in files),
            "statements_removed": 0,
            "unverified_markers": sum(len(f["unverified"]) for f in files),
            "sent_back_to_fix": sum(self.fix_rounds.values()),
        }
