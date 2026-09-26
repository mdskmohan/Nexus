"""Starter review playbooks.

A playbook is a firm's checklist for reviewing one kind of document: for each
position, what the firm wants (`standard`), what it can live with
(`fallback`), and what must always be raised (`red_flags`).

These starters encode widely used commercial-contract review points. They are
NOT a statement of any jurisdiction's law and have NOT been approved by a
lawyer at any firm. Every firm gets its own copy, marked as a starter, and
the product shows that status on every review until a named lawyer at the
firm has reviewed and approved the playbook (see docs/legal/playbooks.md).
"""

NDA = {
    "slug": "nda",
    "name": "Non-disclosure agreement (NDA)",
    "document_type": "NDA / confidentiality agreement",
    "description": "Review an NDA for the protections a party normally needs, whether it is "
                   "disclosing, receiving, or both (mutual).",
    "positions": [
        {
            "id": "definition",
            "title": "Definition of confidential information",
            "standard": "Clearly defined. Covers information disclosed in any form (written, oral, "
                        "visual, electronic). If marking is required, oral or visual disclosures can be "
                        "identified as confidential afterwards (for example in writing within 30 days), "
                        "or information that a reasonable person would understand to be confidential is covered.",
            "fallback": "A marking requirement for written information only, if oral disclosures are "
                        "rare in the relationship.",
            "red_flags": "Only marked written information is protected, with no route for oral disclosures "
                         "(if our client discloses). Or, if our client receives: a definition so broad it "
                         "covers everything, including information our client already has.",
            "severity": "high",
        },
        {
            "id": "exclusions",
            "title": "Standard exclusions",
            "standard": "Information is excluded if it (1) is or becomes public other than through the "
                        "recipient's breach, (2) was already lawfully known to the recipient, (3) is "
                        "independently developed without use of the confidential information, or (4) is "
                        "received from a third party with no duty of confidentiality.",
            "fallback": "The exclusions are present but the recipient must prove them with written records.",
            "red_flags": "Any of the four standard exclusions is missing (if our client receives). "
                         "Exclusions that go wider than these four (if our client discloses).",
            "severity": "high",
        },
        {
            "id": "compelled_disclosure",
            "title": "Disclosure required by law",
            "standard": "The recipient may disclose where required by law, regulation, court order or a "
                        "regulator, provided it gives prompt notice where lawful, cooperates with efforts to "
                        "obtain protective treatment, and discloses only what is legally required.",
            "fallback": "Notice 'where practicable' rather than 'prompt' notice.",
            "red_flags": "No permission to disclose where legally compelled, or no notice obligation at all.",
            "severity": "medium",
        },
        {
            "id": "purpose",
            "title": "Permitted use (the purpose)",
            "standard": "The recipient may use the information only for a clearly described purpose.",
            "fallback": "A general purpose ('evaluating a potential business relationship') if the "
                        "relationship is still early.",
            "red_flags": "No use restriction, or the purpose is undefined, circular or open-ended.",
            "severity": "high",
        },
        {
            "id": "recipients",
            "title": "Who may receive the information",
            "standard": "Disclosure limited to employees, officers, professional advisers (and, if "
                        "needed, affiliates or financing sources) who need to know it for the purpose and "
                        "are bound by confidentiality duties at least as protective. The recipient is "
                        "responsible for their compliance.",
            "fallback": "Recipient responsible for its representatives' breaches without a requirement "
                        "that they sign a separate undertaking.",
            "red_flags": "Disclosure to any third party permitted, or the recipient is not responsible "
                         "for breaches by the people it shares with.",
            "severity": "medium",
        },
        {
            "id": "term",
            "title": "Duration of the obligations",
            "standard": "Confidentiality obligations last a defined period after disclosure or "
                        "termination that fits the information (commonly 2 to 5 years), and trade secrets "
                        "stay protected for as long as they remain trade secrets.",
            "fallback": "A single fixed period with no separate trade-secret protection, if no trade "
                        "secrets are expected to be shared.",
            "red_flags": "Obligations end when the agreement ends, or no duration is stated at all. "
                         "(An indefinite term may be unenforceable in some jurisdictions; flag for the "
                         "lawyer rather than accept or reject automatically.)",
            "severity": "high",
        },
        {
            "id": "return",
            "title": "Return or destruction",
            "standard": "On request or at the end of the relationship, the recipient returns or destroys "
                        "the information, with a carve-out for copies kept in routine backups or to comply "
                        "with law, which stay confidential.",
            "fallback": "Destruction only, with written certification on request.",
            "red_flags": "No obligation to return or destroy, or retained copies are not kept confidential.",
            "severity": "low",
        },
        {
            "id": "no_licence",
            "title": "No licence or warranty",
            "standard": "No licence or other rights in the information are granted, and information is "
                        "provided 'as is', without warranty as to accuracy or completeness.",
            "fallback": "No licence stated; warranty point silent.",
            "red_flags": "Any language that could be read as granting a licence or ownership of the "
                         "information or of resulting developments.",
            "severity": "medium",
        },
        {
            "id": "remedies",
            "title": "Remedies",
            "standard": "Acknowledges that breach may cause irreparable harm and that the discloser may "
                        "seek injunctive or other equitable relief in addition to other remedies.",
            "fallback": "Silent on remedies (general law applies).",
            "red_flags": "Liquidated damages, uncapped indemnities, penalty clauses or one-sided fee "
                         "shifting (if our client receives). Any clause limiting the discloser to damages "
                         "only (if our client discloses).",
            "severity": "medium",
        },
        {
            "id": "restrictive_covenants",
            "title": "Non-solicitation, non-compete or exclusivity",
            "standard": "None. An NDA normally does not restrict hiring, competition or dealing with others.",
            "fallback": "A narrow, time-limited non-solicitation of employees the parties met through the "
                        "discussions, with a general-advertising exception.",
            "red_flags": "Any non-compete, exclusivity or broad non-solicit. Enforceability of these "
                         "varies sharply by jurisdiction; always flag for the lawyer.",
            "severity": "high",
        },
        {
            "id": "residuals",
            "title": "Residuals clause",
            "standard": "None.",
            "fallback": "A residuals clause limited to information retained in unaided memory, excluding "
                        "trade secrets and anything covered by patents or copyright.",
            "red_flags": "A broad residuals clause letting the recipient use whatever its people remember.",
            "severity": "medium",
        },
        {
            "id": "law_forum",
            "title": "Governing law and disputes",
            "standard": "A stated governing law and forum (courts or arbitration) acceptable to our client.",
            "fallback": "Governing law stated without an exclusive forum.",
            "red_flags": "No governing law, or a law or forum with no connection to either party.",
            "severity": "medium",
        },
        {
            "id": "assignment",
            "title": "Assignment",
            "standard": "Neither party may assign without the other's consent, except to a successor in a "
                        "merger or sale of the business.",
            "fallback": "No assignment clause.",
            "red_flags": "The other party may assign freely while our client may not.",
            "severity": "low",
        },
    ],
}

COMMERCIAL = {
    "slug": "commercial",
    "name": "Commercial agreement essentials",
    "document_type": "Services, supply, licence or other commercial agreement",
    "description": "First-pass review of the terms that carry most of the risk in a commercial "
                   "contract: liability, indemnities, termination, IP, payment and renewal.",
    "positions": [
        {
            "id": "liability_cap",
            "title": "Limitation of liability",
            "standard": "Each party's total liability is capped (commonly by reference to fees paid or "
                        "payable over 12 months), and indirect or consequential losses are excluded, with "
                        "sensible exceptions (for example fraud, wilful misconduct, confidentiality breach, "
                        "indemnified claims, and liability that cannot be limited by law).",
            "fallback": "A cap that is higher (for example 2x annual fees) or a separate higher cap for "
                        "data breaches.",
            "red_flags": "No cap, a cap that protects only the other party, or exclusions so broad that "
                         "the main remedy for non-performance is excluded.",
            "severity": "high",
        },
        {
            "id": "indemnities",
            "title": "Indemnities",
            "standard": "Indemnities are limited to specific risks (such as third-party IP infringement "
                        "claims), with a defined claims procedure (notice, control of defence, cooperation).",
            "fallback": "Mutual indemnities for third-party claims caused by breach of law.",
            "red_flags": "Broad or uncapped indemnities given by our client, especially for 'any losses "
                         "arising out of or in connection with' the agreement.",
            "severity": "high",
        },
        {
            "id": "termination",
            "title": "Termination rights",
            "standard": "Either party may terminate for material breach not cured within a stated period "
                        "(commonly 30 days) and for insolvency. Any termination for convenience is mutual "
                        "and on reasonable notice.",
            "fallback": "Termination for convenience available to the customer only, with payment for "
                        "work done.",
            "red_flags": "Only the other party can terminate, no cure period, or termination for "
                         "convenience without notice or payment for work done.",
            "severity": "high",
        },
        {
            "id": "renewal",
            "title": "Term and automatic renewal",
            "standard": "A defined term. Any automatic renewal can be stopped by notice given a reasonable "
                        "time before renewal.",
            "fallback": "Automatic renewal with a short notice window, flagged for the client's diary.",
            "red_flags": "Automatic renewal with a long or hard-to-meet notice window, or price increases "
                         "on renewal without a cap.",
            "severity": "medium",
        },
        {
            "id": "payment",
            "title": "Fees and payment",
            "standard": "Fees and payment terms are clear, with a reasonable period to pay and a process "
                        "for disputing invoices.",
            "fallback": "Payment period shorter than preferred.",
            "red_flags": "Unilateral right to change fees, high late-payment interest, or the right to "
                         "suspend performance without notice.",
            "severity": "medium",
        },
        {
            "id": "ip",
            "title": "Intellectual property",
            "standard": "Each party keeps its existing IP. Ownership of anything created under the contract "
                        "is stated clearly and matches the commercial deal, with any licences needed to use "
                        "the deliverables.",
            "fallback": "Supplier keeps ownership and grants a broad, perpetual licence to use deliverables.",
            "red_flags": "Ownership of new work is not addressed, or our client's existing IP is "
                         "assigned or licensed more widely than needed.",
            "severity": "high",
        },
        {
            "id": "confidentiality",
            "title": "Confidentiality",
            "standard": "Mutual confidentiality obligations with standard exclusions, surviving termination.",
            "fallback": "Confidentiality covered by a separate NDA that is expressly referenced.",
            "red_flags": "No confidentiality protection, or protection for one party only.",
            "severity": "medium",
        },
        {
            "id": "data_protection",
            "title": "Personal data",
            "standard": "If personal data is processed, the contract contains (or references) data "
                        "processing terms appropriate to the applicable data-protection law.",
            "fallback": "A commitment to agree data processing terms before any personal data is shared.",
            "red_flags": "Personal data will clearly be processed but the contract is silent.",
            "severity": "medium",
        },
        {
            "id": "assignment_control",
            "title": "Assignment and change of control",
            "standard": "No assignment without consent, except to a successor in a merger or sale of the "
                        "business.",
            "fallback": "Assignment to affiliates permitted on notice.",
            "red_flags": "The other party may assign freely, or a change of control of our client lets "
                         "the other party terminate.",
            "severity": "low",
        },
        {
            "id": "law_forum",
            "title": "Governing law and disputes",
            "standard": "A stated governing law and forum acceptable to our client, with any escalation "
                        "or mediation steps workable in practice.",
            "fallback": "Governing law stated without an exclusive forum.",
            "red_flags": "No governing law, or a law or forum with no connection to either party.",
            "severity": "medium",
        },
        {
            "id": "force_majeure",
            "title": "Force majeure",
            "standard": "Performance is excused for events beyond a party's reasonable control, with a "
                        "notice obligation and a right to terminate if the event lasts too long. Payment "
                        "obligations are not excused.",
            "fallback": "No force majeure clause (general law applies).",
            "red_flags": "A one-sided clause, or one that excuses the other party's core obligations "
                         "indefinitely.",
            "severity": "low",
        },
    ],
}

STARTERS = [NDA, COMMERCIAL]
