"""Starter review playbooks for contracts governed by Indian law.

These encode review points widely raised by Indian commercial practitioners,
with the statute or leading Supreme Court authority behind each where one
exists. They are a starting point for a firm's own positions, not legal
advice, and have not been approved by a lawyer at any firm (see
docs/legal/playbooks.md). Where the answer turns on facts, state law or
unsettled case law, the position tells the reviewer to flag it rather than
decide it.
"""

_ARBITRATION = {
    "id": "disputes",
    "title": "Dispute resolution (arbitration or courts)",
    "standard": "If arbitration: the clause names the seat (not just a 'venue'), the number of arbitrators, "
                "the appointment procedure (or an arbitral institution such as MCIA, IAC or DIAC), and the "
                "language, under the Arbitration and Conciliation Act, 1996. Appointment is neutral: neither "
                "party alone appoints a sole arbitrator. If courts: an exclusive jurisdiction clause chooses "
                "courts that already have jurisdiction (where a party resides or the cause of action arises).",
    "fallback": "Arbitration seated in a city acceptable to our client with a three-member tribunal, or "
                "non-exclusive jurisdiction of courts in our client's city.",
    "red_flags": "A sole arbitrator appointed unilaterally by the other party, or appointed from a panel only "
                 "that party controls (the Supreme Court has held such clauses invalid, e.g. Perkins Eastman, "
                 "2019). 'Venue' named with no seat. Exclusive jurisdiction given to courts with no connection "
                 "to the contract. Arbitration and court jurisdiction clauses that contradict each other.",
    "severity": "high",
}

_STAMP = {
    "id": "stamp_execution",
    "title": "Stamp duty, execution and signing",
    "standard": "The contract states who bears stamp duty and is to be stamped under the applicable State "
                "stamp law before or at execution. Signatories and their authority are stated. Electronic "
                "signature is used only where the Information Technology Act, 2000 allows it for this kind of "
                "document.",
    "fallback": "Silent on who pays, with our client able to stamp it before relying on it.",
    "red_flags": "Obligation on our client alone to pay stamp duty on a high-value instrument without "
                 "agreement. Note for the lawyer: an unstamped or under-stamped instrument cannot be admitted "
                 "in evidence until duty and penalty are paid (Indian Stamp Act, 1899, s.35 and State "
                 "equivalents).",
    "severity": "medium",
}

_DPDP = {
    "id": "personal_data",
    "title": "Personal data (DPDP Act)",
    "standard": "Where personal data of individuals will be shared or processed, the contract allocates roles "
                "(data fiduciary and data processor), limits processing to the stated purpose, requires "
                "reasonable security safeguards and breach notification, and deals with deletion at the end, "
                "consistent with the Digital Personal Data Protection Act, 2023 and rules made under it.",
    "fallback": "A commitment to sign data-processing terms before any personal data is shared.",
    "red_flags": "Personal data will clearly be processed but the contract is silent, or our client, as data "
                 "fiduciary, has no control over a processor's use of the data.",
    "severity": "medium",
}

NDA_IN = {
    "slug": "nda-india",
    "name": "NDA (Indian law)",
    "document_type": "Non-disclosure / confidentiality agreement governed by Indian law",
    "description": "NDA review for Indian-law agreements: the standard NDA points plus the Indian Contract "
                   "Act, stamping, arbitration and data-protection points Indian practitioners raise.",
    "positions": [
        {"id": "definition", "title": "Definition of confidential information",
         "standard": "Covers information disclosed in any form (written, oral, visual, electronic). If marking "
                     "is required, oral or visual disclosures can be identified as confidential in writing "
                     "within a short period (for example 30 days).",
         "fallback": "Marking required for written information only, if oral disclosures will be rare.",
         "red_flags": "Only marked written information is protected (if our client discloses). A definition so "
                      "wide it covers information our client already has (if our client receives).",
         "severity": "high"},
        {"id": "exclusions", "title": "Standard exclusions",
         "standard": "Excludes information that is public (not through breach), already lawfully known, "
                     "independently developed, or received from a third party without restriction.",
         "fallback": "Exclusions present, with the recipient to prove them by written records.",
         "red_flags": "Any of the four standard exclusions missing (if our client receives).",
         "severity": "high"},
        {"id": "compelled_disclosure", "title": "Disclosure required by law or a regulator",
         "standard": "Disclosure allowed where required by law, a court, or a regulator (for example SEBI, RBI "
                     "or a tax authority), with prompt prior notice where lawful and disclosure limited to what "
                     "is required.",
         "fallback": "Notice 'where practicable'.",
         "red_flags": "No carve-out for legally compelled disclosure.",
         "severity": "medium"},
        {"id": "purpose_recipients", "title": "Purpose and permitted recipients",
         "standard": "Use limited to a defined purpose. Disclosure only to employees, directors and advisers "
                     "who need to know and are bound by similar duties; the recipient is responsible for them.",
         "fallback": "Group companies added as permitted recipients on the same terms.",
         "red_flags": "No purpose limit, or disclosure to any third party.",
         "severity": "high"},
        {"id": "term", "title": "Duration of the obligations",
         "standard": "Confidentiality survives for a defined period after termination suited to the information "
                     "(commonly 2 to 5 years), longer for trade secrets.",
         "fallback": "A single fixed period if no trade secrets are expected.",
         "red_flags": "Obligations end when the agreement ends, or no duration is stated.",
         "severity": "high"},
        {"id": "restraint_of_trade", "title": "Non-compete, non-solicit, exclusivity (s.27)",
         "standard": "No restraint on either party carrying on its business. Under s.27 of the Indian Contract "
                     "Act, 1872, an agreement restraining anyone from a lawful profession, trade or business is "
                     "void to that extent (the only statutory exception is sale of goodwill).",
         "fallback": "A narrow, time-limited non-solicitation of employees introduced through the discussions, "
                     "with a general-advertising exception. Flag for the lawyer: enforceability of "
                     "non-solicitation clauses under s.27 depends on their breadth and the facts.",
         "red_flags": "Any non-compete or exclusivity, or a broad no-hire clause. Always flag for the lawyer "
                      "with the s.27 point.",
         "severity": "high"},
        {"id": "remedies", "title": "Remedies and damages",
         "standard": "Either party may seek injunctive relief (Specific Relief Act, 1963) in addition to damages.",
         "fallback": "Silent (general law applies).",
         "red_flags": "Liquidated damages or penalties payable by our client. Note for the lawyer: under s.74 of "
                      "the Indian Contract Act, only reasonable compensation up to the stated sum is recoverable, "
                      "not the sum as such. Uncapped indemnities from our client.",
         "severity": "medium"},
        {"id": "return", "title": "Return or destruction",
         "standard": "Return or destroy on request or at the end, with retained backup or legally required copies "
                     "kept confidential.",
         "fallback": "Destruction with written certification on request.",
         "red_flags": "No return or destruction obligation.",
         "severity": "low"},
        _ARBITRATION,
        {"id": "governing_law", "title": "Governing law",
         "standard": "Indian law governs.",
         "fallback": "Foreign law only where one party is foreign and our client agrees.",
         "red_flags": "No governing law. Foreign governing law between two Indian parties: flag for the lawyer.",
         "severity": "medium"},
        _STAMP,
        _DPDP,
    ],
}

SERVICES_IN = {
    "slug": "services-india",
    "name": "Services / commercial agreement (Indian law)",
    "document_type": "Services, supply or other commercial agreement governed by Indian law",
    "description": "First-pass review of an Indian-law commercial agreement: liability, indemnities, payment "
                   "and taxes, MSME payment rules, termination, IP, disputes, stamping and data protection.",
    "positions": [
        {"id": "scope", "title": "Scope, deliverables and acceptance",
         "standard": "Services and deliverables are described specifically, with timelines and an objective "
                     "acceptance process.",
         "fallback": "Scope in a schedule or statement of work referenced by the agreement.",
         "red_flags": "Vague scope, or deemed acceptance on delivery with no chance to test.",
         "severity": "medium"},
        {"id": "payment_tax", "title": "Fees, GST and TDS",
         "standard": "Fees stated with whether GST is included or extra; invoices must be GST-compliant; the "
                     "payer may deduct tax at source (TDS) as the Income-tax law requires and give certificates; "
                     "a reasonable period to pay and to dispute invoices.",
         "fallback": "GST extra with invoicing details in a schedule.",
         "red_flags": "Silence on whether fees include GST. A gross-up obligation on our client for TDS. "
                      "Unilateral fee changes. High penal interest.",
         "severity": "medium"},
        {"id": "msme", "title": "MSME supplier payment terms",
         "standard": "If the supplier is a micro or small enterprise registered under the MSMED Act, 2006, the "
                     "buyer pays within the agreed period, which cannot exceed 45 days from acceptance; late "
                     "payment attracts compound interest at three times the bank rate (ss.15-16).",
         "fallback": "Not applicable where the supplier is not a micro or small enterprise; ask the client.",
         "red_flags": "Payment terms longer than 45 days where our client buys from a micro or small enterprise "
                      "(exposure to statutory interest), or where our client is the MSME and the terms ignore "
                      "these rights.",
         "severity": "medium"},
        {"id": "liability_cap", "title": "Limitation of liability",
         "standard": "Each party's total liability capped (commonly by reference to fees paid in the last 12 "
                     "months); indirect and consequential loss excluded; exceptions for fraud, wilful "
                     "misconduct, confidentiality and data breaches, and indemnified third-party claims.",
         "fallback": "A higher cap, or a separate higher cap for data breaches.",
         "red_flags": "No cap on our client's liability, or a cap protecting only the other party.",
         "severity": "high"},
        {"id": "indemnities", "title": "Indemnities",
         "standard": "Limited to specific risks (third-party IP infringement, breach of law), with notice, "
                     "control of defence and mitigation. Note: s.124 of the Indian Contract Act defines "
                     "indemnity narrowly; the drafting should state what is covered.",
         "fallback": "Mutual indemnities for third-party claims caused by breach.",
         "red_flags": "Broad 'any loss arising out of or in connection with' indemnities from our client, "
                      "uncapped.",
         "severity": "high"},
        {"id": "liquidated_damages", "title": "Liquidated damages and penalties",
         "standard": "Any liquidated damages are a genuine pre-estimate and capped. Note for the lawyer: under "
                     "s.74 only reasonable compensation up to the stated sum is recoverable.",
         "fallback": "Service credits as the sole remedy for service-level failures, capped.",
         "red_flags": "Uncapped or cumulative penalties payable by our client.",
         "severity": "medium"},
        {"id": "termination", "title": "Termination",
         "standard": "Either party may terminate for material breach not cured within a stated period (commonly "
                     "30 days) and for insolvency; any termination for convenience is mutual with notice and "
                     "payment for work done.",
         "fallback": "Customer-only termination for convenience with payment for work done.",
         "red_flags": "Only the other party can terminate, no cure period, or no payment for work done.",
         "severity": "high"},
        {"id": "ip", "title": "Intellectual property",
         "standard": "Each party keeps its existing IP; ownership of new work is stated clearly. An assignment of "
                     "copyright is in writing and states the rights, duration and territory (Copyright Act, "
                     "1957, s.19).",
         "fallback": "Supplier keeps ownership and grants a broad, perpetual licence.",
         "red_flags": "Ownership of new work not addressed; an assignment that omits duration or territory "
                      "(s.19(5)-(6) then default it to five years and India).",
         "severity": "high"},
        {"id": "confidentiality", "title": "Confidentiality",
         "standard": "Mutual obligations with standard exclusions, surviving termination.",
         "fallback": "A separate NDA expressly referenced.",
         "red_flags": "No confidentiality protection, or one-sided protection.",
         "severity": "medium"},
        {"id": "force_majeure", "title": "Force majeure",
         "standard": "Defined events, notice, mitigation, and a right to terminate if prolonged; payment "
                     "obligations not excused. Without a clause, only the narrow doctrine of frustration under "
                     "s.56 applies.",
         "fallback": "A general force majeure clause without a termination right.",
         "red_flags": "One-sided force majeure, or none in a long-term supply contract.",
         "severity": "low"},
        _ARBITRATION,
        _STAMP,
        _DPDP,
    ],
}

EMPLOYMENT_IN = {
    "slug": "employment-india",
    "name": "Employment agreement (Indian law)",
    "document_type": "Employment agreement or appointment letter governed by Indian law",
    "description": "Review of an Indian employment agreement or appointment letter from the employer's or the "
                   "employee's side: restraints, notice, IP, confidentiality and statutory benefits.",
    "positions": [
        {"id": "role_pay", "title": "Role, place of work and pay",
         "standard": "Designation, duties, place of work, transfer terms, CTC with its breakdown, and variable "
                     "pay criteria are stated.",
         "fallback": "Details in an annexure or offer letter referenced by the agreement.",
         "red_flags": "Unilateral right to cut pay; unlimited transfer rights without notice.",
         "severity": "medium"},
        {"id": "probation_notice", "title": "Probation, notice and termination",
         "standard": "Probation period and confirmation stated; notice periods for both sides stated and "
                     "reasonable; pay in lieu of notice allowed; termination for cause defined.",
         "fallback": "Longer notice for senior roles, with garden leave.",
         "red_flags": "Notice periods very different for employer and employee; a bond or penalty for leaving "
                      "early (flag for the lawyer: courts test such amounts for reasonableness under s.74).",
         "severity": "high"},
        {"id": "post_employment_restraint", "title": "Post-employment non-compete (s.27)",
         "standard": "No restraint on the employee working in the same field after employment ends. Under s.27 "
                     "of the Indian Contract Act, 1872, post-employment non-compete covenants are generally "
                     "unenforceable; restrictions during employment (including exclusivity) are generally valid.",
         "fallback": "Confidentiality and a narrowly drawn non-solicitation of clients or employees for a short "
                     "period, flagged for the lawyer as its enforceability depends on breadth.",
         "red_flags": "Any post-employment non-compete. Always flag, with the s.27 point, whichever side we act for.",
         "severity": "high"},
        {"id": "confidentiality_ip", "title": "Confidentiality and IP assignment",
         "standard": "Confidentiality continues after employment; work created in the course of employment "
                     "belongs to the employer, with an assignment clause and moral-rights and cooperation "
                     "language.",
         "fallback": "Reliance on the Copyright Act default (employer owns works made in the course of "
                     "employment under a contract of service, s.17(c)) plus confidentiality.",
         "red_flags": "No IP clause for a role that creates software, designs or content.",
         "severity": "medium"},
        {"id": "statutory_benefits", "title": "Statutory benefits and policies",
         "standard": "Refers to provident fund, gratuity, leave, and applicable policies (including the POSH "
                     "policy under the Sexual Harassment of Women at Workplace Act, 2013) as applicable to the "
                     "establishment.",
         "fallback": "A general reference to benefits 'as per applicable law and company policy'.",
         "red_flags": "Terms that purport to waive statutory entitlements.",
         "severity": "medium"},
        {"id": "disputes_law", "title": "Governing law and disputes",
         "standard": "Indian law; courts or arbitration in the city of employment.",
         "fallback": "Courts at the employer's head office.",
         "red_flags": "Arbitration with an arbitrator appointed only by the employer; courts with no connection "
                      "to the employment.",
         "severity": "medium"},
        _DPDP,
    ],
}

INDIA = [NDA_IN, SERVICES_IN, EMPLOYMENT_IN]
