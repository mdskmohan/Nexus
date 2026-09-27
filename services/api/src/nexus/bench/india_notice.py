"""Nexus India legal-notice benchmark: section 138 cheque-dishonour notices.

Varied, fictional cases (amounts from thousands to crores, different banks,
reasons and date styles). For each, the real pipeline drafts the notice and
the result is scored automatically:

- completed: a notice passed the fact checks and was saved
- first_time_right: it matched every entered fact without being sent back
- no_extra_demand: the notice demands no sum other than the cheque amount
  (a demand for more than the cheque amount can make the notice defective)
- cites_section_138: the notice names section 138 of the NI Act

Dates and amounts are computed by code, so timeline correctness is covered by
the unit tests, not scored here.
"""

import json
import re
import time

from nexus import tasks
from nexus.ai.adapters import ModelRef
from nexus.bench.lab import _bench_firm
from nexus.db import row, scalar, tenant
from nexus.india.cheque import rupees

ADVOCATE = {"advocate_name": "Adv. Kavita Deshmukh", "advocate_address": "Office 12, Lawyers' Chambers, Pune 411001",
            "enrolment_number": "MAH/5678/2012"}

CASES = [
    {"payee_name": "Shree Ganesh Traders", "payee_address": "12 MG Road, Nashik 422001",
     "drawer_name": "Mr. Rakesh Kulkarni", "drawer_address": "45 College Road, Nashik 422005",
     "cheque_number": "004512", "cheque_date": "2026-08-20", "amount": 450000,
     "bank": "State Bank of India, Nashik Road Branch", "presented_on": "2026-09-10",
     "information_received_on": "2026-09-15", "reason": "Funds insufficient",
     "liability": "payment for goods supplied under invoices dated 1 and 15 July 2026"},
    {"payee_name": "Mrs. Lakshmi Iyer", "payee_address": "Flat 3B, Lake View Apartments, Chennai 600041",
     "drawer_name": "Mr. Suresh Menon", "drawer_address": "22 Anna Nagar West, Chennai 600040",
     "cheque_number": "117890", "cheque_date": "2026-07-01", "amount": 1250000,
     "bank": "HDFC Bank, Anna Nagar Branch", "presented_on": "2026-08-25",
     "information_received_on": "2026-08-28", "reason": "Payment stopped by drawer",
     "liability": "repayment of a friendly loan of Rs. 12,50,000 advanced on 5 March 2026"},
    {"payee_name": "Apex Steel Private Limited", "payee_address": "Plot 7, MIDC Bhosari, Pune 411026",
     "drawer_name": "Om Sai Fabricators", "drawer_address": "Shed 14, Industrial Estate, Chakan 410501",
     "cheque_number": "000231", "cheque_date": "2026-09-01", "amount": 28750500,
     "bank": "Bank of Maharashtra, Chakan Branch", "presented_on": "2026-09-05",
     "information_received_on": "2026-09-08", "reason": "Exceeds arrangement",
     "liability": "the price of steel coils supplied between April and June 2026"},
    {"payee_name": "Dr. Farhan Qureshi", "payee_address": "14 Banjara Hills, Road No. 3, Hyderabad 500034",
     "drawer_name": "Ms. Priya Reddy", "drawer_address": "8-2-293 Jubilee Hills, Hyderabad 500033",
     "cheque_number": "552109", "cheque_date": "2026-06-30", "amount": 75000,
     "bank": "ICICI Bank, Jubilee Hills Branch", "presented_on": "2026-09-20",
     "information_received_on": "2026-09-22", "reason": "Account closed",
     "liability": "arrears of rent for the months of April to June 2026 for premises at Banjara Hills"},
    {"payee_name": "Gupta Cloth Emporium", "payee_address": "Chandni Chowk, Delhi 110006",
     "drawer_name": "M/s Kapoor Garments", "drawer_address": "Karol Bagh, New Delhi 110005",
     "cheque_number": "300018", "cheque_date": "2026-09-12", "amount": 318400,
     "bank": "Punjab National Bank, Karol Bagh Branch", "presented_on": "2026-09-14",
     "information_received_on": "2026-09-18", "reason": "Drawer's signature differs",
     "liability": "the balance due for fabric supplied under bill no. 4471 dated 20 August 2026"},
]


def _extra_demand(content: str, amount: int) -> list[str]:
    """Rupee sums in the notice other than the cheque amount."""
    found = re.findall(r"(?:Rs\.?|₹|INR)\s*([\d,]+)", content)
    return sorted({f for f in found if f.replace(",", "") and int(f.replace(",", "")) != amount})


def run_case(case: dict, model: ModelRef, progress=print) -> dict:
    firm = _bench_firm()
    facts = {**case, **ADVOCATE}
    started = time.monotonic()
    with tenant(firm) as s:
        matter_id = scalar(s, "INSERT INTO matters (firm_id, name) VALUES (:f, :n) RETURNING id",
                           f=firm, n=f"Notice bench: {case['payee_name']} v {case['drawer_name']}")
        run_id = scalar(s, """INSERT INTO runs (firm_id, matter_id, kind, title, input)
                              VALUES (:f, :m, 'notice', :t, CAST(:i AS jsonb)) RETURNING id""",
                        f=firm, m=matter_id, t=f"Notice bench {case['cheque_number']}",
                        i=json.dumps({"facts": facts}))
    tasks.run_agent(firm, {"run_id": str(run_id)}, model=model)
    with tenant(firm) as s:
        run = row(s, "SELECT status, error, output, guardrails, cost_usd FROM runs WHERE id = :r", r=run_id)
    result = {"case": case["cheque_number"], "status": run["status"], "error": run["error"],
              "seconds": round(time.monotonic() - started, 1), "cost_usd": float(run["cost_usd"])}
    if run["status"] == "needs_review":
        content = run["output"]["content"]
        extra = _extra_demand(content, case["amount"])
        result.update(completed=True, first_time_right=run["guardrails"].get("sent_back_to_fix", 0) == 0,
                      no_extra_demand=not extra, extra_sums=extra,
                      cites_section_138=bool(re.search(r"(section|sec\.?|s\.)\s*138", content, re.I)))
    else:
        result.update(completed=False)
    progress(f"  cheque {case['cheque_number']} (Rs. {rupees(case['amount'])}): {run['status']}"
             + ("" if result["completed"] else f" ({run['error']})"))
    return result


def run(model: ModelRef, progress=print) -> dict:
    results = [run_case(c, model, progress) for c in CASES]
    done = [r for r in results if r["completed"]]
    n = len(results)
    return {
        "benchmark": "nexus-india-cheque-notice",
        "cases": n,
        "completed": len(done) / n,
        "first_time_right": sum(r["first_time_right"] for r in done) / n,
        "no_extra_demand": sum(r["no_extra_demand"] for r in done) / n,
        "cites_section_138": sum(r["cites_section_138"] for r in done) / n,
        "cost_usd": round(sum(r["cost_usd"] for r in results), 4),
        "results": results,
    }
