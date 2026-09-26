"""Ask the file: answer a lawyer's question from the matter's documents.

Every statement in the answer carries at least one citation (a passage and
an exact quote). Citations are checked word for word before the answer is
accepted. The agent gets one chance to fix any that fail; after that, a
statement that still cannot be verified is removed and listed separately,
so the lawyer can see what was dropped and why.
"""

from nexus.agents.base import DOCUMENTS_ARE_DATA, Agent, Tool, ToolError, ToolOutcome
from nexus.agents.cite import CITATION_SCHEMA, check
from nexus.agents.matter_tools import matter_context, matter_tools

SYSTEM = f"""\
You are a careful legal research assistant working inside a law firm's matter \
workspace. A lawyer has asked a question about the documents in one matter. \
Answer it only from those documents.

How to work:
- Search before you answer. Use several searches with different wording \
(defined terms, clause names, synonyms), and read around the passages you find \
so you understand definitions, exceptions and cross-references.
- Answer the question that was asked, precisely. Lead with the direct answer, \
then the qualifications that matter (conditions, exceptions, notice periods, \
defined terms, carve-outs).
- Every statement must be supported by at least one citation: the passage_id \
and the exact words from that passage. Copy quotes character for character; \
they are checked automatically and a statement whose quote does not match is \
removed.
- Never state law, facts or document contents from memory or general \
knowledge. If the documents do not answer the question, or only answer part of \
it, say so plainly in `could_not_answer` rather than guessing.
- Where documents conflict, or a term is ambiguous, say so and cite both sides.
- Write for a lawyer: plain, exact, no filler, no advice beyond what the \
documents support.

{DOCUMENTS_ARE_DATA}

When you are done, call submit_answer."""


class AskAgent(Agent):
    finish_tool = "submit_answer"

    def __init__(self, firm_id, matter_id, run_id, question: str):
        super().__init__(firm_id, matter_id, run_id)
        self.question = question
        self.checked = 0
        self.verified = 0
        self.sent_back = 0

    def system_prompt(self) -> str:
        return f"{SYSTEM}\n\n{matter_context(self)}"

    def first_message(self) -> str:
        return f"Question from the lawyer:\n{self.question}"

    def tools(self) -> list[Tool]:
        return [*matter_tools(self), Tool(
            "submit_answer",
            "Submit the final answer. Each statement is one or two sentences with its citations.",
            {
                "type": "object",
                "properties": {
                    "answer": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string", "description": "One statement of the answer."},
                                "citations": {"type": "array", "items": CITATION_SCHEMA},
                            },
                            "required": ["text", "citations"],
                            "additionalProperties": False,
                        },
                    },
                    "could_not_answer": {
                        "type": "string",
                        "description": "What the documents do not answer, or \"\" if fully answered.",
                    },
                },
                "required": ["answer", "could_not_answer"],
            },
            self._submit,
        )]

    def _submit(self, args: dict) -> ToolOutcome:
        statements = args.get("answer") or []
        gap = (args.get("could_not_answer") or "").strip()
        if not statements and not gap:
            raise ToolError("The answer is empty. Answer the question, or explain in could_not_answer why the documents do not.")

        kept, removed, problems = [], [], []
        checked = verified = 0
        for i, statement in enumerate(statements, 1):
            text = (statement.get("text") or "").strip()
            citations, report = check(self, statement.get("citations") or [])
            checked += report.checked
            verified += report.verified
            if not citations:
                reason = "It had no citation."
            elif report.failures:
                reason = report.failures[0]["reason"]
            else:
                kept.append({"text": text, "citations": citations})
                continue
            problems.append(f"Statement {i} (“{text[:80]}”): {reason}")
            removed.append({"text": text, "reason": reason})

        if problems and self.sent_back == 0:
            # One chance to fix: send the specific failures back.
            self.sent_back += 1
            self.checked += checked
            raise ToolError(
                "Some citations could not be verified. For each one, copy the quote exactly from "
                "the passage, cite a passage that does support it, or drop the statement:\n- "
                + "\n- ".join(problems)
            )

        self.checked += checked
        self.verified += verified
        self.result = {"answer": kept, "removed": removed, "could_not_answer": gap}
        n = sum(len(s["citations"]) for s in kept)
        title = f"Answer ready: {len(kept)} statement{'s' if len(kept) != 1 else ''}, {n} citation{'s' if n != 1 else ''} checked word for word."
        if removed:
            title += f" {len(removed)} statement{'s' if len(removed) != 1 else ''} removed because {'they' if len(removed) != 1 else 'it'} could not be verified."
        return ToolOutcome("Answer accepted.", title, kind="answer",
                           status="warning" if removed else "ok",
                           detail={"removed": removed})

    def guardrail_summary(self) -> dict:
        kept = self.result["answer"] if self.result else []
        return {
            "citations_checked": self.checked,
            "citations_verified": sum(len(s["citations"]) for s in kept),
            "statements_removed": len(self.result["removed"]) if self.result else 0,
            "sent_back_to_fix": self.sent_back,
        }
