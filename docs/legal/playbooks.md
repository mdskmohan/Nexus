# Review playbooks

A playbook is how a firm tells Nexus what "good" looks like for one kind of
contract. It is the firm's legal judgement, written down, and it is the most
important input to a contract review.

## Structure

Each playbook has a list of **positions**. Each position has:

| Field | Meaning | Example (NDA, duration) |
|---|---|---|
| Title | The point being reviewed | Duration of the obligations |
| What we want (`standard`) | The firm's preferred position | Obligations last a defined period after disclosure or termination (commonly 2–5 years); trade secrets protected for as long as they remain trade secrets |
| What we can accept (`fallback`) | The acceptable compromise | A single fixed period with no trade-secret carve-out, if no trade secrets will be shared |
| Always raise (`red_flags`) | What must be flagged | Obligations that end when the agreement ends, or no duration at all |
| Default risk (`severity`) | How serious a shortfall usually is | High |

For each position the review agent records one finding (meets, deviates,
missing, or needs the lawyer's judgement) with the contract language it relies
on and, where needed, proposed wording.

## Perspective matters

Whether a clause is good depends on who you act for. A narrow definition of
confidential information helps a recipient and hurts a discloser. Every review
asks **who we act for**, and the starter playbooks state their red flags from
both sides where it matters ("if our client receives…", "if our client
discloses…").

## The starter playbooks

Nexus gives every firm two starters:

1. **Non-disclosure agreement (NDA)**, 13 positions: definition, standard
   exclusions, compelled disclosure, purpose, permitted recipients, duration,
   return or destruction, no licence or warranty, remedies, restrictive
   covenants, residuals, governing law and disputes, assignment.
2. **Commercial agreement essentials**, 11 positions: limitation of
   liability, indemnities, termination, term and renewal, fees and payment,
   IP, confidentiality, personal data, assignment and change of control,
   governing law and disputes, force majeure.

**How they were written.** They encode review points that are widely treated
as standard in commercial practice across common-law jurisdictions. The
positions are deliberately general. Where the answer turns on local law (for
example the enforceability of non-competes or indefinite confidentiality
terms), the starters tell the reviewer to flag the point for the lawyer rather
than decide it.

**What they are not.** They are not a statement of the law of any jurisdiction,
and they have not been approved by any lawyer at your firm. Until a partner
approves them, every review that uses them says so, in the product and in the
review memo.

## Approval

1. A partner opens the playbook under *Review playbooks* and reads every position.
2. The partner edits positions to match the firm's practice: jurisdictions,
   typical clients, negotiating stance.
3. The partner approves it, confirming they are a qualified lawyer at the firm
   and that it reflects the firm's position. Their name and the date are
   recorded, and the approval is written to the audit trail.
4. **Any later edit removes the approval**, so the approved version is always
   the one in use.

## Writing good positions

- Write **what we want** as a test someone could apply to a clause, not as a
  preference. "Liability capped at 12 months' fees" is testable; "reasonable
  cap" is not.
- Put the **walk-away point** in *always raise*. That is what the reviewer must
  never let pass silently.
- Say **when local law decides the point**, so the reviewer marks it for
  judgement instead of guessing.
- Keep positions **independent**: one topic each, so each finding is clear.
