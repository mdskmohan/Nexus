# Scope and limitations

Knowing where a tool stops is part of using it competently. This page is
deliberately blunt.

## What Nexus does

- Answers questions **from the documents in a matter**, quoting its sources.
- Reviews a contract **against a playbook** the firm controls, and proposes
  wording.
- Drafts memos, schedules and letters **from the documents in a matter**,
  with sources for every fact.
- Checks every quote it relies on, word for word, against the source text.

## What Nexus does not do

- **It does not give legal advice.** Its output is a draft for a lawyer.
- **It does not research law.** It has no access to case law, legislation or
  commentary databases, and it is instructed not to state law as fact. When a
  point depends on the law of a jurisdiction, reviews mark it for the lawyer's
  judgement.
- **It does not know what is not in the file.** A missing amendment, side
  letter or later email can change the answer. Nexus cannot tell that a
  document is missing unless the documents themselves refer to it.
- **It does not verify that documents are genuine, final or current.**
- **It does not read images.** Scanned PDFs, photos and handwritten notes need
  OCR before upload. Charts and images inside documents are not read.

## What the citation check guarantees, and what it does not

| Guaranteed | Not guaranteed |
|---|---|
| Every quote shown as **✓ Checked** appears, word for word, in the cited passage of the cited document | That the quote supports the statement it is attached to |
| Statements whose quotes could not be verified are removed (answers) or marked **[unverified]** (drafts) | That nothing relevant was missed |
| Quotes come only from the current matter | That the AI's reasoning or legal analysis is correct |

The check removes the most dangerous failure, invented sources, but it does
not remove the need for a lawyer to read the source in context.

## Known failure modes

- **Missed provisions.** Search is keyword-based and the AI searches with
  several wordings, but unusually worded clauses can be missed. Reviews require
  a finding for every playbook point, and "missing" findings should be checked.
- **Over-reliance on one document** when several conflict. The agents are told
  to prefer the most recent or most specific document and to point out
  conflicts, but they can get this wrong.
- **Defined terms and cross-references** spread across long documents can be
  misread.
- **Tracked-change placement.** In the Word redline, a changed paragraph keeps
  the formatting of its first run, so mixed formatting within that paragraph
  (for example a bold defined term) is simplified. Suggestions that cannot be
  located in the Word file are listed in the review memo instead.
- **Spreadsheets** are read as text, row by row. Formulas are read as their
  last saved values, and very large sheets are truncated (5,000 rows per sheet).

## Starter playbooks

The starter playbooks reflect widely used commercial review points. They are
not specific to any jurisdiction and are not a substitute for the firm's own
positions. See [Review playbooks](playbooks.md).
