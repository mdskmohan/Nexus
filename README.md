# Nexus

**An AI legal team for every firm, with every answer checked against your documents.**

Nexus reads a matter's documents and does the work a firm needs from them:

- **Ask**: answers questions about the file, and every statement links to the exact words it relies on.
- **Review**: checks a contract against the firm's playbook, clause by clause, and returns a review memo
  and a Word copy with the suggested changes as tracked changes.
- **Draft**: writes memos, schedules and client updates as Word or Excel files, and every fact carries a source.

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
| Agents | Ask, contract review against playbooks, drafting (Word/Excel); bounded steps and spend |
| Guardrails | Word-for-word citation checks; matter-scoped tools; database-enforced firm isolation; hidden-instruction and sensitive-number scans; human sign-off by role; append-only audit trail |
| Observability | Live plain-language activity for every task; tokens, cost and timing per task; firm-wide safety dashboard |
| Documents | PDF, Word, Excel, PowerPoint, email, text; search by clause and heading |
| Product | Matters, team roles, firm preferences read by every task, playbooks with lawyer approval |
| Benchmarks | LegalBench (incl. CUAD, ContractNLI, MAUD) and Harvey LAB, with official data and graders |

## Quick start

Requirements: Docker, Python 3.12 with [uv](https://docs.astral.sh/uv/), Node.js 20.9+.

```bash
cp .env.example .env          # add ANTHROPIC_API_KEY and a NEXUS_JWT_SECRET
make dev                      # database, API, worker and web app
cd services/api && uv run nexus-seed-demo   # optional: a demo firm with a sample NDA
```

Open http://localhost:3100.

```bash
make test                     # backend tests against a real Postgres
```

## Documentation

- **[User guide](docs/user-guide.md)**: for lawyers and legal staff
- **[Legal framework](docs/legal/README.md)**: professional responsibility, confidentiality, limitations, playbooks
- **[Technical documentation](docs/README.md)**: architecture, agents, guardrails, API, security, deployment, benchmarks

## Status

The platform runs locally and its test suite passes. The AI agents have not yet been exercised against
the live model in this repository's history; that is the next step, followed by benchmark runs. Before
production: SSO and MFA, rate limiting, object storage with
encryption, and an independent security review ([details](docs/technical/security.md#before-production-not-yet-done)).
The starter review playbooks need approval by a qualified lawyer before firms rely on them.
