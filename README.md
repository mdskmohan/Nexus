# Nexus

**An AI legal team for Indian law firms, with every answer checked against your documents.**

Nexus reads a matter's documents and does the work a firm needs from them. It is built first for Indian
firms and advocates:

- **Ask**: answers questions about the file, and every statement links to the exact words it relies on.
- **Review**: checks a contract against the firm's playbook, clause by clause, and returns a review memo
  and a Word copy with the suggested changes as tracked changes.
- **Draft**: writes memos, lists of dates and events, schedules and client updates as Word or Excel files,
  and every fact carries a source.
- **Notices**: drafts section 138 cheque-dishonour notices, with the statutory deadlines computed in code and
  every fact checked against what the advocate entered.

Before a lawyer sees anything, **every quote is verified word for word against the source document**.
Statements that cannot be verified are removed or visibly marked, never presented as sourced.

> The previous product in this repository (a data-pipeline control plane) is preserved at the git tag
> `archive/data-pipelines-v0`.

---

## Why this can win

Harvey sells top-down to large firms and enterprise legal departments. Most of the market, the small
and mid-size firms and solo practitioners, does the same kinds of work with far fewer people and is
underserved. Nexus starts there and grows up-market, on three rules:

1. **Big-firm quality, small-firm effort.** Sign up, add documents, and get useful, checked work in
   minutes. No sales call, no implementation project.
2. **Nothing unverified reaches the lawyer.** Provenance is checked in code, not requested in a prompt
   ([ADR-002](docs/adr/ADR-002-verify-citations-in-code.md)).
3. **Agents do whole tasks.** "Review this NDA against our playbook, mark it up and draft the cover
   note" is one request with one reviewable result.

## What is built

| Area | |
|---|---|
| Agents | Ask, contract review against playbooks, drafting (Word/Excel), section 138 notices; bounded steps and spend |
| AI models | Bring your own: Claude, GPT, Gemini, OpenAI-compatible or on-premises; encrypted keys; model per task |
| India | Indian-law playbooks (NDA, services, employment); s.138 timeline; lakh/crore amounts |
| Guardrails | Word-for-word citation checks; matter-scoped tools; database-enforced firm isolation; hidden-instruction and sensitive-number scans; human sign-off by role; append-only audit trail |
| Observability | Live plain-language activity for every task; tokens, cost and timing per task; firm-wide safety dashboard |
| Documents | PDF, Word, Excel, PowerPoint, email, text; search by clause and heading |
| Product | Matters, team roles, firm preferences read by every task, playbooks with lawyer approval |
| Benchmarks | LegalBench (incl. CUAD, ContractNLI, MAUD), Harvey LAB, and Nexus India benchmarks (contract review, notices, chronology) |

## Quick start

Requirements: Docker, Python 3.12 with [uv](https://docs.astral.sh/uv/), Node.js 20.9+.

```bash
cp .env.example .env          # set NEXUS_JWT_SECRET and NEXUS_SECRET_KEY
make dev                      # database, API, worker and web app
cd services/api && uv run nexus-seed-demo   # optional: a demo firm with a sample NDA
```

Open http://localhost:3100 and connect an AI model in Firm settings → AI models.

```bash
make test                     # backend tests against a real Postgres
```

## Documentation

- **[User guide](docs/user-guide.md)**: for lawyers and legal staff
- **[Legal framework](docs/legal/README.md)**: professional responsibility, confidentiality, limitations, playbooks
- **[Technical documentation](docs/README.md)**: architecture, agents, guardrails, API, security, deployment, benchmarks

## Status

**Built:** matters and documents (PDF, Word, Excel, PowerPoint, email, text); ask, contract review, drafting
and section 138 notices; Indian-law and general review playbooks; bring-your-own AI (Claude, GPT, Gemini,
OpenAI-compatible and on-premises models) with encrypted keys; guardrails, activity record, audit trail,
sign-off, stopping tasks and recovery after a crash. 59 automated tests pass against a real Postgres.

**Proven live:** the full question-answering flow on a local model (correct answer, verified quote);
connecting a model and testing the connection; a real provider rejecting a bad key; stopping a task;
recovery of interrupted tasks.

**Not yet proven live:** contract review, drafting and notices end to end, and every benchmark. They need a
capable model; the local model on the development laptop (8 GB M1) is too slow and runs out of memory.
No benchmark numbers exist yet.

**Before production:** SSO and MFA, rate limiting, object storage with encryption, an independent security
review ([details](docs/technical/security.md#before-production-not-yet-done)), and approval of the starter
playbooks and benchmark answer keys by a practising lawyer.
