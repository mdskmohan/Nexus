# Nexus

**An AI legal team for firms that can't afford Harvey.**

Nexus gives a 5-lawyer firm the same agentic legal AI a 2,000-lawyer firm gets:
agents that read the matter file, do the work, cite every claim to its source,
and hand back something a lawyer can sign off on.

> The previous product in this repo (a data-pipeline control plane) is preserved
> at the git tag `archive/data-pipelines-v0`.

---

## Why this can win

Harvey sells top-down to big law and enterprise legal departments: long sales
cycles, custom deployments, pricing to match. That leaves most of the market
unserved — the tens of thousands of small and mid-size firms and solo
practitioners who do the same kinds of work with far fewer people.

We start there and grow up-market. Three rules:

1. **Big-firm quality, small-firm effort.** Sign up, drop in documents, get
   useful work back in the first ten minutes. No sales call, no onboarding project.
2. **Nothing unverified reaches the lawyer.** Every statement links to the page
   and passage it came from. A citation we cannot verify is not shown. Invented
   case law gets lawyers sanctioned; this is the trust line we never cross.
3. **Agents do whole tasks, not chat turns.** "Review this NDA against our
   playbook, redline it, and draft the cover email" is one request with one
   reviewable result.

## What we build first

Work where correctness can be checked against the documents themselves — so we
can ship without licensed case-law databases or an in-house legal expert:

| # | Capability | What the lawyer gets |
|---|---|---|
| 1 | **Matter workspace** | Upload a matter's files; everything is searchable and citable to page and passage |
| 2 | **Ask the file** | Answers about the documents, each sentence linked to its source |
| 3 | **Contract review agent** | Clause-by-clause issues against a firm playbook, with a redlined .docx |
| 4 | **Drafting from the firm's own precedents** | First drafts that follow how *this* firm writes |
| 5 | **Firm memory** | Preferences and playbooks learned once, applied to every task |

Later: legal research with verified citations (starting from public sources
such as CourtListener), Word and Outlook add-ins, integrations with practice
management tools (Clio, MyCase), and multi-step agents that chain tasks together.

## Known gaps

- **No legal expert on the team yet.** Until we have one, "correct" is defined
  only where it can be checked against source documents. Playbooks and review
  checklists must be validated by practising lawyers before any are presented as
  legal standards. Recruiting a lawyer advisor is the first non-code task.
- **Security and confidentiality** are table stakes for law firms (client
  privilege, no training on customer data, data residency). These are designed
  in from the first commit, not added later.
