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
