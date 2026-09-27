# Agents

All agents share one loop (`nexus/agents/base.py`) and one set of research
tools (`nexus/agents/matter_tools.py`). They differ in their system prompt,
their finishing tool, and the checks that tool enforces. The loop talks to
models through `nexus/ai/adapters.py`, so it is the same for every provider.

## The loop

```
model = the run's chosen model, else the firm default (nexus/ai/registry.py)
system prompt (+ firm preferences + matter context)
user message (the task)
repeat up to max_steps:
    stop if someone pressed "Stop task"
    turn = complete(model, conversation, tools)   # provider-neutral
    meter tokens (and cost, if the model is priced); stop over the token or money limit
    stop on refusal; stop if truncated with no tool call
    if no tool calls: nudge (agent-specific: names what is missing), at most twice
    run every tool call; record each as a step; return results (errors flagged)
    if the finishing tool accepted the work: return the result
```

Properties that matter for legal work:

- **Bounded.** `NEXUS_AGENT_MAX_STEPS` (30 by default; review 60, draft 80) and
  `NEXUS_AGENT_BUDGET_USD` ($5 by default) per run.
- **Append-only conversation.** The system prompt and tools never change within
  a run and history is never edited, which keeps prompt caching effective and
  thinking blocks valid.
- **Finishing tools can say no.** A `ToolError` from the finishing tool goes
  back to the model as an error result with the specific problems. After
  `max_finish_attempts` (3) rejections the run stops with the last problem shown
  to the lawyer.
- **Providers** (`nexus/ai/adapters.py`): Anthropic (adaptive thinking, effort,
  automatic prompt caching, server-side refusal fallbacks), OpenAI (strict
  function schemas, reasoning effort for reasoning models), Google Gemini
  (function declarations with JSON Schema; thought signatures echoed back),
  and OpenAI-compatible endpoints. Provider-native assistant content is echoed
  back unchanged. Missing keys, rejected keys, unknown models and unreachable
  endpoints raise `ModelUnavailable`, with one message for lawyers and one for
  the admin setting things up.
- **Interrupted runs.** A run whose worker died is marked interrupted (never
  left running); the job of a dead worker on the same host is reclaimed at once.

## Research tools

| Tool | Does |
|---|---|
| `list_documents` | Documents in the matter with ids and passage counts |
| `search(query, document_id)` | Full-text search; returns passages with id, document, location, heading, full text |
| `read(document_id, start_position, count)` | Consecutive passages, up to 8, for reading in order or around a hit |

The tools are closures over one matter (and, for review, one document). No tool
takes a matter or firm id, so there is no parameter for the model to point
elsewhere. All tool schemas are strict, with every property required (optional
inputs use `""`).

## Ask (`agents/ask.py`)

Finishing tool: `submit_answer(answer[{text, citations[{passage_id, quote}]}], could_not_answer)`.

Checks: every statement needs at least one citation; every citation's passage
must be in the matter and its quote must verify. First failure: the specific
problems go back to the model to fix. Second submission: statements that still
fail are **removed** from the answer and listed under `removed` with the
reason.

## Review (`agents/review.py`)

Tools: `search`, `read` (pinned to the contract), `record_finding`, `finish_review`.

- `record_finding(position_id, status, risk, passage_id, quote, explanation, suggested_language)`:
  `meets`, `deviates` and `unclear` need a verified quote from the contract
  under review. `deviates` and `missing` need suggested language. A failing
  quote is rejected immediately, so the finding is never stored unverified.
- `finish_review(summary, client_note)`: rejected until every playbook
  position has a finding.

Outputs: findings, issues sorted by risk, summary, client note, the review memo
(.docx), and for Word originals a tracked-changes copy (`redline.py`), with
`w:del`/`w:ins` revisions authored "Nexus (AI draft)" and a margin comment
carrying each explanation.

## Draft (`agents/draft.py`)

Tools: research tools, `write_deliverable(filename, content, sources[])`, `finish(summary)`.

- Content is Markdown with `[S1]`-style markers; each marker's source names a
  passage and an exact quote.
- Failing or undeclared sources are sent back (up to 2 rounds per file). After
  that the file is accepted, and failing markers render as **[unverified]**
  and are counted in the guardrail summary.
- `finish` is rejected until every requested deliverable exists.
- `deliverables.py` renders `.docx` (headings, lists, bold/italic, tables,
  superscript source numbers, a Sources section), `.xlsx` (one sheet per
  table) or `.md`.

## Legal notice (`agents/notice.py`)

First notice type: demand notice for a dishonoured cheque under s.138 NI Act.
The lawyer's form supplies the facts; `nexus/india/cheque.py` computes the
statutory timeline (validity, 30-day notice window, 15-day payment window,
one-month complaint limitation) and the amount in figures and words. The AI
only drafts. `write_notice` runs `fact_checks`: the cheque number, amount in
figures and words, cheque date (in any common Indian format), bank, both
names, the reason for dishonour and the 15-day demand must all appear, or the
draft goes back to the AI. The notice is rendered to Word.

## Adding an agent

1. Subclass `Agent`: `system_prompt`, `first_message`, `tools`,
   `guardrail_summary`, and set `finish_tool`.
2. Put every check that must hold in the finishing tool (or an intermediate
   tool, like `record_finding`) and raise `ToolError` with a specific,
   fixable message.
3. Add the run kind to the `runs_kind_check` constraint (new migration), to
   `tasks._build_agent`, and an endpoint that calls `_start_run`.
4. Add a result component in `apps/web/components/task/`.
