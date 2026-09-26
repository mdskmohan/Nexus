# Professional responsibility

Lawyers' professional rules apply to work done with AI tools in the same way
they apply to work done by junior lawyers, paralegals or outside vendors.
Regulators have said this directly. In the United States, the American Bar
Association's **Formal Opinion 512** (July 2024) addresses lawyers' use of
generative AI under the Model Rules. In England and Wales, the **Solicitors
Regulation Authority** and **the Law Society** have published guidance on AI.
Many state bars and other regulators have issued similar guidance.

The duties below are the ones those sources consistently raise. For each one,
we describe what Nexus does and what remains the firm's responsibility. Rule
numbers refer to the ABA Model Rules; equivalents exist in most jurisdictions.

---

## Competence (Model Rule 1.1)

*A lawyer must understand the capabilities and limitations of the tools they
use, and must independently verify their output as appropriate.*

**What Nexus does**
- Shows its work. The *What the AI did* panel lists every search and every
  document read, in plain language.
- Makes verification fast. Each statement links to the exact quoted words and
  the document they come from.
- States its limits in the product: [Scope and limitations](limitations.md).

**The firm's responsibility**
- Train users on what the tool does and does not do (the
  [user guide](../user-guide.md) is written for this).
- Check the substance. Nexus guarantees a quote is really in the document; it
  cannot guarantee the quote means what the AI says it means, or that the
  document is complete, current or authentic.

## Confidentiality (Model Rule 1.6)

*A lawyer must make reasonable efforts to prevent unauthorised disclosure of
client information, which includes understanding how a tool stores, uses and
shares the information entered into it.*

**What Nexus does**
- The AI can read only the documents in the matter it is working on. The
  research tools are bound to a single matter and take no parameter that
  could reach another.
- Each firm's data is separated by the database (Postgres row-level security).
  A query that forgot to filter by firm still returns nothing from another firm.
- Document text is sent to the AI provider only to perform the task requested.
  See [Data handling](data-handling.md).

**The firm's responsibility**
- Decide whether the client's informed consent is needed before using an AI
  tool on their matter. ABA Formal Opinion 512 indicates informed consent is
  required before inputting client information into self-learning tools that
  could disclose it to others. Whether it is needed for tools like Nexus that do
  not train on client data depends on the circumstances and the applicable rules.
- Check engagement letters and client guidelines. Some clients prohibit or
  restrict AI tools.
- Confirm the AI provider's current terms and retention settings for your
  deployment.

## Communication (Model Rule 1.4)

*Clients may need to be told how AI is used on their matter, especially when it
affects the scope, cost or approach of the work.*

**What Nexus does:** records which AI tasks were run on each matter, by whom,
and what they cost, so the firm can explain its use accurately.

**The firm's responsibility:** decide what to tell clients, and when.

## Candour to the tribunal and meritorious claims (Model Rules 3.1, 3.3)

*Lawyers have been sanctioned for filing briefs citing cases that an AI tool
invented, most prominently in* Mata v. Avianca, Inc. *(S.D.N.Y. 2023).*

**What Nexus does**
- Does not cite case law or statutes as facts. It works only from the matter's
  documents.
- Verifies every quote against its source before the lawyer sees it, and
  removes or visibly marks anything it cannot verify.
- Tells the drafting agent not to invent facts, cases or statutes, and to say
  so when the documents do not contain what is needed.

**The firm's responsibility:** anything filed with a court or sent to an
opposing party must be checked by a lawyer against primary sources. Nexus's
checks do not replace that.

## Supervision (Model Rules 5.1, 5.3)

*Partners and supervising lawyers must have measures in place so that the work
of lawyers and non-lawyers, including work done with AI tools, meets the
lawyer's professional obligations.*

**What Nexus does**
- **Sign-off.** AI output is a draft until an associate, partner or admin
  approves it. The approval, the approver and any note are recorded.
- **Roles.** Paralegals can run tasks but cannot approve them. Only partners
  can change or approve the firm's review playbooks and preferences.
- **Audit trail.** An append-only record of who uploaded, ran, approved and
  downloaded what, which nobody can edit or delete.
- **Playbook approval.** Starter playbooks are marked as unapproved until a
  named lawyer at the firm approves them, and any edit clears the approval.

**The firm's responsibility:** set a policy for who may use Nexus, on which
matters, and what level of review each kind of output needs before it leaves
the firm.

## Fees (Model Rule 1.5)

*Fees must be reasonable. ABA Formal Opinion 512 indicates lawyers who bill by
the hour may bill only for time actually spent, not for time saved by AI, and
should not bill clients for time spent learning a general-purpose tool.*

**What Nexus does:** shows the actual cost of every AI task, per matter and
firm-wide, on the *Safety & activity* page.

**The firm's responsibility:** decide how, and whether, AI costs and
AI-assisted work are reflected in fees and engagement terms.

---

## A suggested firm policy (starting point)

1. Nexus may be used on client matters unless the client has restricted AI use.
2. AI output is never sent outside the firm until a lawyer has approved it in
   Nexus and checked every point it relies on.
3. Nothing produced by Nexus is filed with a court or tribunal without a lawyer
   checking every statement against primary sources.
4. Partners approve each review playbook before it is used on client work, and
   re-approve after changes.
5. The practice-management partner reviews the *Safety & activity* page monthly.

Adapt this to your jurisdiction, practice areas and client base.
