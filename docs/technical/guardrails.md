# Guardrails

Each guardrail is enforced in code (or by the database), not by asking the
model nicely. The table lists what enforces it and what tests it.

| Guardrail | Enforced by | Tested in |
|---|---|---|
| Every quote verified word for word | `guardrails/citations.py`, `agents/cite.py`, finishing tools | `test_guardrails.py::TestCitations` |
| Unverifiable statements removed (ask) or marked (draft) | `agents/ask.py`, `agents/draft.py`, `deliverables.py` | `test_deliverables.py` |
| AI sees only the current matter | `agents/matter_tools.py` (closures, scoped SQL) | by construction; see below |
| Firms cannot see or write each other's data | Postgres RLS (`migrations/0001`) | `test_platform.py::test_firms_cannot_see_each_other`, `test_cannot_write_into_another_firm` |
| Documents cannot instruct the AI | `DOCUMENTS_ARE_DATA` in every system prompt; scan on upload | `test_guardrails.py::TestScan` |
| Sensitive numbers flagged | `guardrails/scan.py` | `test_guardrails.py::TestScan::test_sensitive_numbers` |
| Human sign-off, by role | `api/work.py` (`require("associate")`) | `test_platform.py::test_roles_limit_who_can_approve_and_edit` |
| Step and spending limits | `agents/base.py` | loop logic |
| Audit trail cannot be altered | trigger + revoked grants (`migrations/0001`) | `test_platform.py::test_audit_trail_is_append_only` |
| Playbook approval cleared on edit | `api/work.py::update_playbook` | `test_platform.py::test_editing_a_playbook_clears_its_approval` |

## Citation verification

`verify_quote(quote, passage_text)`:

1. Normalise both sides: Unicode NFKC; curly quotes, dashes and non-breaking
   spaces to plain equivalents; words hyphenated across line breaks re-joined;
   whitespace collapsed; lower case.
2. Split the quote on ellipses (`…` or `...`); each fragment must appear in the
   passage, **in order**.
3. Reject quotes shorter than 12 characters in total: too short to show where a
   statement comes from.

What it deliberately does not do: fuzzy matching. A quote with one word changed
fails. The cost is an occasional send-back; the benefit is that "✓ Checked"
means exactly what it says.

## Hidden-instruction scan

Patterns (case-insensitive) for text addressed to an AI: "ignore/disregard …
previous … instructions", references to a system prompt, attempts to redefine
the AI's role, "do not tell the user…", "respond only with…", and model control
tokens. A match flags the document with the page and an excerpt. It does not
block the document: the text may be legitimate evidence (for example, in a
dispute about an AI system), and the agents treat all document text as data
regardless.

## Why the database, not the application, isolates firms

Each request sets `app.firm_id` for its transaction (`db.tenant()`). Every
tenant table has `ENABLE` and `FORCE ROW LEVEL SECURITY` with a policy of
`firm_id = current_setting('app.firm_id')`. The application connects as
`nexus_app`, which does not own the tables and cannot bypass RLS. Two narrow
exceptions exist and are documented in the migration: the job queue (claimed
across firms by the worker, which then switches into the job's firm) and the
`auth_lookup(email)` function used by login, which returns only the fields
login needs.
