from datetime import date

from nexus.agents.notice import ChequeNotice, date_variants, fact_checks
from tests.conftest import add_local_model, signup

FACTS = dict(
    payee_name="Shree Ganesh Traders", payee_address="12 MG Road, Nashik 422001",
    drawer_name="Mr. Rakesh Kulkarni", drawer_address="45 College Road, Nashik 422005",
    cheque_number="004512", cheque_date="2026-01-10", amount=450000,
    bank="State Bank of India, Nashik Road Branch", presented_on="2026-02-02",
    information_received_on="2026-02-05", reason="Funds insufficient",
    liability="payment for goods supplied under invoices dated 1 and 15 December 2025",
    advocate_name="Adv. Meera Joshi", advocate_address="Chamber 4, District Court, Nashik",
)

GOOD = """**Legal Notice under Section 138 of the Negotiable Instruments Act, 1881**

To, Mr. Rakesh Kulkarni, 45 College Road, Nashik 422005

Under instructions from and on behalf of my client, Shree Ganesh Traders, I serve you with this notice.

1. You owe my client payment for goods supplied under invoices dated 1 and 15 December 2025.
2. Towards discharge of that liability you issued cheque No. 004512 dated 10 January 2026 for Rs. 4,50,000/- (Rupees Four Lakh Fifty Thousand only) drawn on State Bank of India, Nashik Road Branch.
3. The cheque was presented on 2 February 2026 and returned unpaid with the remark "Funds insufficient", of which my client received information on 5 February 2026.
4. I call upon you to pay the said amount within 15 (fifteen) days of receipt of this notice, failing which my client will initiate proceedings under Section 138 read with Section 142 of the Act at your risk as to costs.

Adv. Meera Joshi"""


def test_a_notice_that_matches_the_facts_passes():
    assert fact_checks(GOOD, ChequeNotice.from_input(FACTS)) == []


def test_mismatched_facts_are_caught():
    n = ChequeNotice.from_input(FACTS)
    wrong_words = GOOD.replace("Four Lakh Fifty Thousand", "Forty Five Thousand")
    assert any("amount in words" in p for p in fact_checks(wrong_words, n))
    wrong_number = GOOD.replace("004512", "004521")
    assert any("cheque number" in p for p in fact_checks(wrong_number, n))
    no_demand = GOOD.replace("within 15 (fifteen) days", "immediately")
    assert any("15 (fifteen) days" in p for p in fact_checks(no_demand, n))
    other_date = GOOD.replace("10 January 2026", "11 January 2026")
    assert any("cheque date" in p for p in fact_checks(other_date, n))


def test_common_date_styles_are_accepted():
    variants = date_variants(date(2026, 1, 10))
    assert "10.01.2026" in variants and "10th January 2026" in variants and "10th day of January, 2026" in variants
    n = ChequeNotice.from_input(FACTS)
    assert fact_checks(GOOD.replace("10 January 2026", "10.01.2026"), n) == []


def test_notice_endpoint_validates_and_queues(client):
    signup(client)
    matter = client.post("/api/matters", json={"name": "Shree Ganesh v Kulkarni"}).json()
    add_local_model(client)
    bad = {**FACTS, "presented_on": "2026-01-01"}  # before the cheque date
    assert client.post(f"/api/matters/{matter['id']}/notices/cheque", json=bad).status_code == 422
    r = client.post(f"/api/matters/{matter['id']}/notices/cheque", json=FACTS)
    assert r.status_code == 201
    run = client.get(f"/api/runs/{r.json()['id']}").json()
    assert run["kind"] == "notice" and run["status"] == "queued"


def test_timeline_endpoint(client):
    signup(client)
    t = client.post("/api/notices/cheque/timeline", json={
        "cheque_date": "2026-01-10", "presented_on": "2026-02-02", "information_received_on": "2026-02-05",
        "amount": 450000}).json()
    assert t["notice_last_day"] == "2026-03-07" and t["amount_words"] == "Rupees Four Lakh Fifty Thousand only"
    assert client.post("/api/notices/cheque/timeline", json={"cheque_date": "x"}).status_code == 422
