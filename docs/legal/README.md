# Legal framework

This section explains how Nexus is designed around a lawyer's professional
duties, what it does and does not do, and what a firm must decide before using
it. It is written for partners, general counsel, risk and compliance teams, and
anyone assessing Nexus for a law firm.

> **This is not legal advice.** It describes the product and the professional
> considerations that commonly apply to lawyers' use of AI tools. Each firm must
> assess its own obligations under the rules of the jurisdictions where it
> practises.

| Document | What it covers |
|---|---|
| [Professional responsibility](professional-responsibility.md) | How the product maps to the duties of competence, confidentiality, supervision, candour and fair billing |
| [Data handling and confidentiality](data-handling.md) | What data goes where, isolation between clients and firms, retention, the AI provider |
| [Scope and limitations](limitations.md) | What Nexus does, what it does not do, and known failure modes |
| [Review playbooks](playbooks.md) | How playbooks work, how the starters were written, and the approval process |

## The principles behind the design

1. **The lawyer decides.** Nexus drafts and checks; a lawyer approves. Every
   output is a draft until someone at the firm approves it, and the approval is
   recorded.
2. **Grounded, never invented.** Nexus answers only from the matter's
   documents. Every statement of fact carries a quote, and every quote is
   verified word for word against the source before a lawyer sees it.
   Statements that cannot be verified are removed or marked. They are never
   shown as if they were sourced.
3. **Say what is not known.** When the documents do not answer a question, the
   product says so. When an answer depends on local law or facts outside the
   file, the review marks it for the lawyer's judgement instead of guessing.
4. **Confidentiality by construction.** Each matter is a closed world for the
   AI, and each firm's data is separated by the database itself, not by the
   AI's good behaviour.
5. **A record that cannot be changed.** Uploads, AI tasks, approvals and
   downloads are written to an append-only audit trail.
6. **No hidden instructions.** Documents cannot direct the AI. Text that tries
   to is ignored and flagged.
