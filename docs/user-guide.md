# Nexus user guide

*For advocates, solicitors, paralegals and legal staff. No technical knowledge needed.*

Nexus is an AI assistant for your firm, built first for Indian law firms. It
reads the documents in a matter and does four kinds of work:

- **Answers questions** about the documents, quoting the exact words it relies on.
- **Reviews contracts** against your firm's checklist, including Indian-law
  checklists for NDAs, services agreements and employment agreements.
- **Drafts documents**, such as memos, schedules and client updates, from the file.
- **Drafts legal notices**, starting with cheque-dishonour notices under
  section 138 of the Negotiable Instruments Act, with the statutory deadlines
  worked out for you.

It never works from memory or the internet. Everything it tells you comes from
the documents you gave it, and **every quote is checked word for word** before
you see it.

---

## 1. Getting started

**Setting up your firm.** The first person to sign up creates the firm account
and becomes its administrator. Go to *Firm settings → Team → Add a colleague* to
invite others. Choose a role for each person:

| Role | Can |
|---|---|
| Paralegal | Work on matters, upload documents, run AI tasks |
| Associate | All of the above, plus approve AI work and remove documents |
| Partner | All of the above, plus edit and approve review playbooks, set firm preferences, see the audit trail |
| Admin | All of the above, plus manage the team |

**Connect an AI model.** Nexus works with the AI your firm chooses. An admin
opens *Firm settings → AI models → Add a provider* and picks one:

| Provider | What you need |
|---|---|
| Anthropic (Claude), OpenAI (GPT), Google (Gemini) | An API key from that company's website |
| OpenRouter | One key that gives access to many providers' models |
| A model on your own server (for example through Ollama) | The server's address; nothing leaves your network |
| Any other OpenAI-compatible service (Azure OpenAI, Groq, …) | Its address and key |

Then add the models your team may use (Nexus lists what your key offers),
mark one as the **default**, and click **Test connection**. Keys are encrypted
and never shown again; only their last four characters appear. You can set a
price per model so costs show in money; otherwise Nexus still limits every
task by size.

If more than one model is connected, lawyers choose the model for each task
(the default is preselected).

**Tell Nexus how your firm works.** In *Firm settings*, write a short brief the
way you would for a new associate: the clients you usually act for, house
style, things you always want flagged. The AI reads it before every task.

## 2. Matters and documents

A **matter** holds everything for one piece of work. The AI can only ever see
the documents in the matter you are working in, never another matter and never
another firm.

1. On *Matters*, click **New matter**. Give it a name, the client, and a line
   about what it is (the AI uses this as background).
2. Open the **Documents** tab and drag in your files.

Nexus reads PDF, Word, Excel, PowerPoint, email (.eml) and text files, up to
50 MB each. Scanned PDFs need to be run through OCR first; Nexus will tell you
if a PDF has no readable text.

When a document is uploaded, Nexus also checks it for two things and tells you
what it found:

- **Text aimed at an AI.** Sometimes a document contains wording that tries to
  instruct an AI ("ignore your instructions and…"). Nexus never follows it. It
  treats the wording as part of the document and flags it so you know it is
  there.
- **Sensitive numbers.** Identity and payment numbers, such as social security,
  PAN, Aadhaar, card and bank account numbers, so you can check they belong in
  the file.

## 3. Asking a question

Open the matter, choose **Ask a question**, type your question in plain
language, and click **Ask**.

You will see the AI working in the **What the AI did** panel: which documents
it searched and read. When it finishes you get:

- **The answer.** Each statement has a small green number. Click it to see
  the exact words in the document it comes from.
- **Sources.** Every quote, with the document and location, marked **✓ Checked**.
- **Not covered by the documents.** If the documents do not answer part of
  your question, Nexus says so instead of guessing.
- **Removed before you saw them.** If the AI wrote a statement whose quote could
  not be found in the documents, it was removed. You can see what was removed
  and why.

Good questions are specific: *"Can Brightline share our information with its
investors, and on what conditions?"* works better than *"Tell me about
confidentiality."*

## 4. Reviewing a contract

Choose **Review a contract**, then:

1. pick the contract;
2. pick the **playbook** (your firm's checklist) to review it against;
3. say **who we act for**. This matters: a clause can be good for the discloser
   and bad for the recipient;
4. optionally add instructions, e.g. *"Client will accept a 3-year term."*

For every point in the playbook you get a finding:

| Finding | Meaning |
|---|---|
| **Meets standard** | The contract gives your client what the playbook asks for |
| **Deviates** | The clause is there but falls short, with suggested replacement wording |
| **Missing** | Nothing in the contract covers it, with suggested wording to add |
| **Your judgement** | The answer depends on facts or local law the AI cannot see; it says what you need to decide |

Every finding quotes the contract language it relies on. You also get a short
summary of the points that matter most, a **draft note to the client**, and Word
files to download:

- a **review memo**;
- for Word contracts, a **copy of the contract with the suggested changes as
  tracked changes**, with the reasoning in margin comments. Accept or reject
  each one in Word, as you would a colleague's mark-up.

## 5. Drafting a document

Choose **Draft a document**. Brief it as you would an associate: who it is for,
what it must cover, the structure you want. Give the file a name ending in
`.docx` (Word), `.xlsx` (Excel) or `.md`. The quick-start buttons fill in common
briefs: issues memo, contract schedule, client update.

In the draft, every fact about the matter carries a numbered source, listed at
the end with the exact quote. If a source could not be verified, it shows as
**[unverified]** in the document, so you know exactly what to check. Legal
analysis and judgement are the AI's own. Treat them as a first draft from a
capable junior, not as advice.

## 6. Drafting a legal notice (cheque dishonour, section 138)

Choose **Legal notice** and fill in the form: your client, the drawer, the
cheque (number, date, amount, bank), what it was given for, when it was
presented, when your client learned it had bounced, the bank's reason, and
your details as the advocate.

As you type, the **Statutory timeline** panel shows, calculated by Nexus (not
by the AI):

- whether the cheque was presented within its three-month validity;
- the **last day to send the notice**: 30 days from when your client learned
  of the dishonour, with the days remaining, or a red warning if it has passed.

Nexus also writes the amount the Indian way, in figures and in words
(₹ 4,50,000/- · Rupees Four Lakh Fifty Thousand only).

Click **Draft the notice**. Before you see the draft, Nexus checks that the
cheque number, the amount in figures and in words, the cheque date, the bank,
both names, the bank's reason and the 15-day demand all appear exactly as you
entered them. A draft that gets any of them wrong is sent back to the AI to
fix. You receive the notice as a Word file, ready for your letterhead and
signature.

Once the notice has been served, the complaint must be filed within one month
of the cause of action (after the 15 days to pay run out). Keep the postal
receipts and tracking or acknowledgement as proof of service.

## 7. Stopping a task

While a task is running you can click **Stop task**. What the AI did up to
that point stays in the activity record. If the server restarts in the middle
of a task, the task is marked as interrupted (never left "working") and you
can simply start it again.

## 8. Checking and approving the work

Everything the AI produces is a **draft** until someone at the firm approves it.
At the bottom of each result:

- **Approve** once you have checked it;
- **Send back** if it is not right, with a note saying why.

Your decision, your name and the time are recorded permanently.

**How to check efficiently.** Read the answer or findings. For anything you will
rely on, click the source and read the quoted words in context (*Open
document*). The quote is guaranteed to be in the document; what you are checking
is whether it means what the AI says it means.

## 9. Review playbooks

A playbook is your firm's checklist for one type of contract. For each point it
says **what we want**, **what we can accept** and **what must always be raised**.

Nexus starts every firm with **starter playbooks**:

- **Indian law:** NDA, services / commercial agreement, and employment
  agreement. These raise the points Indian practitioners look for: section 27
  of the Contract Act (non-competes), section 74 (liquidated damages), stamp
  duty, arbitration seat and neutral appointment of arbitrators, MSME payment
  terms, GST and TDS, copyright assignments (section 19) and the Digital
  Personal Data Protection Act, 2023.
- **General:** NDA and commercial agreement, for contracts under other laws.

**No lawyer at your firm has approved them yet.** Reviews that use an
unapproved playbook say so.

A partner should open each playbook (*Review playbooks*), adjust it to the
firm's positions and the jurisdictions you practise in, then approve it. Any
later edit removes the approval until a partner approves it again.

## 10. Safety & activity

The *Safety & activity* page shows, for the last 30 days: how many AI tasks
ran, how many quotes were checked, what was removed, what is waiting for
review, documents that need a look, and what it cost. Partners and admins also
see the **audit trail**, a permanent record of uploads, downloads, AI tasks,
approvals and settings changes that nobody can edit or delete.

## 11. Good practice

- **You remain responsible for the advice.** Nexus is a tool. Check the work
  as you would check a junior's before it goes to a client or a court.
- **Give it the whole file.** It only knows what is in the matter. A missing
  side letter or amendment can change the answer.
- **Say who you act for** in reviews, and put anything the AI should know in
  the matter description or firm preferences.
- **Do not upload what you are not allowed to share.** Check your engagement
  terms and any client restrictions on using AI tools. See
  [Legal framework](legal/README.md).

## 12. Frequently asked questions

**Can the AI see other clients' documents?** No. It can only read the matter you
are working in. Separately, the database blocks one firm's data from another's,
so this does not depend on the AI behaving.

**Does it use the internet or case law databases?** Not today. It works only
from your documents. It will not cite cases or statutes as facts from your file.

**Is our data used to train the AI?** Nexus sends the text it needs to the AI
provider your firm connected, to do the task. Whether that provider may keep or
train on it depends on that provider's terms for API use (Anthropic, OpenAI and
Google each publish theirs); your administrator should confirm them for your
account. A model on your own server keeps everything inside your network. See
[Data handling](legal/data-handling.md).

**What does it cost?** Each task shows its actual cost when it finishes, and
the *Safety & activity* page totals it. Every task has a spending cap ($5 by
default, set by your administrator); a task that reaches it stops and says so.

**It says "AI is not connected yet".** An administrator needs to connect an AI
model in *Firm settings → AI models* (see section 1).

**Which AI model should we use?** Any capable model works; the checks on
quotes and facts are done by Nexus itself, whichever model you choose. Larger
models (for example Claude, GPT or Gemini's top tiers) give better reviews
and drafts. Small models running on an ordinary laptop can answer short
questions but are too slow for full contract reviews.
