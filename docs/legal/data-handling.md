# Data handling and confidentiality

## What is stored, and where

| Data | Where | Notes |
|---|---|---|
| Uploaded documents (original files) | File storage, under a per-firm key | Local disk in development; object storage in production |
| Extracted text, split into passages | Postgres | Used for search and citation checking |
| Questions, reviews, drafts and their results | Postgres | Including every quote and its verification status |
| Step-by-step activity of each AI task | Postgres | Plain-language steps plus technical detail |
| Generated files (memos, tracked-changes copies, drafts) | File storage | Linked to the task that produced them |
| Audit trail | Postgres | Append-only: cannot be updated or deleted |
| Accounts | Postgres | Passwords stored only as Argon2 hashes |

## Separation between firms and between matters

- **Between firms.** Every table that holds firm data is protected by
  Postgres **row-level security**. Each request runs with its firm set on the
  database connection, and the database returns and accepts only that firm's
  rows. The application connects as a role that cannot switch this off. This is
  tested: a raw query with no filter at all still sees only the current firm's
  data, and an attempt to write into another firm is rejected.
- **Between matters.** The AI's research tools are created for one matter at a
  time. They have no parameter that could reach a different matter, and every
  query they run is scoped to that matter.

## What is sent to the AI provider

Each firm chooses its AI provider in *Firm settings → AI models*: Anthropic
(Claude), OpenAI (GPT), Google (Gemini), an OpenAI-compatible service, or a
model running on the firm's own server. To perform a task, Nexus sends the
chosen provider:

- the task instructions (the question, review brief, drafting brief or notice facts);
- the firm's preferences and the matter's name, client and description;
- the text of the passages the AI searches for and reads;
- for reviews, the playbook.

Original files are not sent, only the text the AI needs. The provider is not
given access to the database or file storage.

**Provider terms decide what happens next.** Whether a provider may retain the
data, for how long, and whether it may use it to train or improve its models
depends on that provider's terms for API use and on the firm's account. Paid
API terms from the major providers generally exclude training on customer
content by default, but **some free tiers allow the provider to use submitted
content to improve its products** (at the time of writing, this includes
Google's free Gemini API tier). **Do not send client documents through a free
tier.** The firm must confirm the current terms for the account it connects.
A model on the firm's own server keeps everything inside its network.

**Keys.** A provider key is encrypted in the database (AES-256-GCM, bound to the
firm, under a master key held outside the database), used only by the server
when a task runs, and never shown again after it is saved. Only admins can add,
replace or remove keys; every change is written to the audit trail.

## Retention and deletion

- Removing a document deletes its file and its passages. Earlier results that
  quoted it keep their quotes, so the record of what was relied on stays intact.
- The audit trail is never deleted by the application.
- Matter-level retention and deletion policies (for example on closing a
  matter) should be set by the firm to match its record-keeping obligations.

## Personal data

Matter files routinely contain personal data. The firm remains the controller
(or equivalent) under the data-protection laws that apply to it, for example
the GDPR / UK GDPR or India's Digital Personal Data Protection Act, 2023.
Nexus supports this by:

- keeping each firm's data separate and access-controlled by role;
- flagging identity and payment numbers on upload, so staff can check they
  belong in the file;
- recording access and downloads in the audit trail.

A production deployment should be covered by a data-processing agreement
between the firm and the operator of Nexus, and between the operator and the AI
provider.

## Security summary

See the [technical security documentation](../technical/security.md) for detail.

- Sessions in HTTP-only cookies; cross-site request protection on every change.
- Passwords hashed with Argon2; roles enforced on every request.
- Uploads limited in type and size; files stored under keys that cannot escape
  the firm's storage area.
- Document text is always treated as data, never as instructions to the AI.
