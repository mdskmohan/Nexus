"""The Indian-law playbooks and the India contract-review benchmark data."""

import io

from docx import Document

from nexus.bench.india_review import score
from nexus.ingest.chunk import chunk
from nexus.ingest.extract import DOCX, extract
from nexus.playbooks_india import INDIA
from nexus.samples_india import CASES, contract_docx


def test_every_case_answers_every_position_of_its_playbook():
    playbooks = {p["slug"]: p for p in INDIA}
    for case in CASES:
        positions = {p["id"] for p in playbooks[case["playbook"]]["positions"]}
        assert set(case["expected"]) == positions, case["name"]
        assert set(case["expected"].values()) <= {"issue", "meets", "either"}


def test_india_contracts_ingest_cleanly():
    for case in CASES:
        data = contract_docx(case["clauses"])
        text = "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
        assert "INR" in text or "Rupees" in text or "India" in text
        passages = chunk(extract(data, DOCX))
        assert len(passages) >= 5


def test_scoring():
    expected = {"a": "issue", "b": "issue", "c": "meets", "d": "either"}
    findings = [
        {"position_id": "a", "status": "deviates", "citation": {"verified": True}},
        {"position_id": "b", "status": "meets", "citation": {"verified": True}},
        {"position_id": "c", "status": "unclear", "citation": None},
        {"position_id": "d", "status": "missing", "citation": None},
    ]
    s = score(expected, findings)
    assert (s["caught"], s["issues"], s["missed"]) == (1, 2, ["b"])
    assert s["false_alarms"] == ["c"]
    assert (s["citations"], s["citations_verified"]) == (2, 2)
    assert s["completed_positions"] == 4


def test_india_playbooks_are_offered_to_firms(client):
    from tests.conftest import signup

    signup(client)
    slugs = [p["slug"] for p in client.get("/api/playbooks").json()]
    assert slugs[:3] == ["employment-india", "nda-india", "services-india"]


def test_notice_benchmark_cases_are_valid_and_extra_sums_are_detected():
    from nexus.agents.notice import ChequeNotice
    from nexus.bench.india_notice import ADVOCATE, CASES, _extra_demand

    for case in CASES:
        n = ChequeNotice.from_input({**case, **ADVOCATE})
        assert n.cheque_date <= n.presented_on <= n.information_received_on
    assert _extra_demand("pay Rs. 4,50,000/- and interest of Rs. 20,000", 450000) == ["20,000"]
    assert _extra_demand("pay ₹ 4,50,000/-", 450000) == []


def test_chronology_scoring():
    from nexus.bench.india_chronology import EXPECTED, score

    table = "| Date | Event |\n|---|---|\n" + "\n".join(
        f"| {d.day} {d.strftime('%B %Y')} | {label} [S{i}] |" for i, (d, label) in enumerate(EXPECTED, 1))
    s = score(table, [{"verified": True}] * len(EXPECTED), [])
    assert s["date_recall"] == 1.0 and s["in_order"] and s["sources_verified"] == len(EXPECTED)
    shuffled = table.replace("12 January 2026", "XX").replace("| 15 July 2026", "| 12.01.2026 |x|\n| 15 July 2026")
    s2 = score(shuffled, [], [])
    assert s2["date_recall"] == 1.0 and s2["in_order"] is False
