# Using Nexus in Indian legal practice

Nexus is built first for Indian law firms and advocates. This page collects
the India-specific points. It is not legal advice; confirm each point against
current law and the Bar Council rules that apply to you.

## Confidentiality and privilege

- Communications between an advocate and client made in the course of
  professional employment are protected by section 132 of the Bharatiya
  Sakshya Adhiniyam, 2023 (formerly section 126 of the Indian Evidence Act,
  1872). Using a tool that sends client material to a third party does not in
  itself waive that protection, but the advocate remains responsible for
  keeping the material confidential. Choose a provider whose terms do not allow
  it to use your data, or a model on your own server.
- Nexus keeps each firm's data separate in the database, lets the AI see only
  the matter it is working on, encrypts provider keys, and records every
  upload, AI task, approval and download.

## Personal data (DPDP Act, 2023)

Matter files contain personal data of clients, opponents and witnesses. For
that data your firm is generally a data fiduciary under the Digital Personal
Data Protection Act, 2023, and the AI provider you connect processes it on
your behalf. Put a data-processing arrangement in place with the provider, keep
uploads to what the matter needs, and use Nexus's sensitive-number flags
(PAN, Aadhaar, card and account numbers) to spot data that should not be there.

## Indian-law review playbooks

The Indian starter playbooks (NDA, services agreement, employment agreement)
state the statutory basis for each point: Indian Contract Act, 1872 ss.27, 74
and 124; Arbitration and Conciliation Act, 1996, with the Supreme Court's
rulings against unilateral appointment of arbitrators (for example *Perkins
Eastman Architects v HSCC*, 2019); the Indian Stamp Act, 1899 and State stamp
laws; the MSMED Act, 2006 ss.15-16; the Copyright Act, 1957 ss.17 and 19; and
the DPDP Act, 2023. Where the answer depends on facts or unsettled law (for
example the enforceability of a narrow non-solicitation clause, or whether a
supplier is an MSME), the playbook tells the reviewer to mark the point for the
advocate's judgement. See [Review playbooks](playbooks.md) for approval.

## Cheque-dishonour notices (section 138, NI Act)

How Nexus applies the statute (see `services/api/src/nexus/india/cheque.py`):

| Requirement | Source | What Nexus does |
|---|---|---|
| Cheque presented within its validity (three months from its date) | s.138 proviso (a); RBI instruction effective 1 April 2012 | Checks the presentation date |
| Notice in writing within 30 days of receiving information of dishonour | s.138 proviso (b) | Computes the last day, shows days left, warns if passed |
| Drawer fails to pay within 15 days of receiving the notice | s.138 proviso (c) | Requires the 15-day demand in the draft |
| Complaint within one month of the cause of action | s.142(1)(b); *Saketh India v India Securities*, (1999) 3 SCC 1 | Computes the date once the notice is served |

The notice demands only the cheque amount. Demanding other sums (interest,
costs, notice charges) as part of the cheque amount is a common ground of
challenge; if the client also claims other amounts, the advocate should state
them separately and clearly, or pursue them separately.

## What is not built yet

- Case-law research (for example through licensed Indian case-law databases).
- Documents in Indian languages other than English (the AI models can read
  many of them, but Nexus's search and checks are tuned for English).
- Court-fee and limitation calculators beyond section 138.
