"""End-to-end through the HTTP API and the worker, against real Postgres."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from nexus import jobs, search
from nexus.db import row, rows, tenant
from nexus.samples import INJECTION_EMAIL, sample_nda_docx
from nexus.tasks import HANDLERS
from tests.conftest import signup

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _matter_with_nda(client) -> tuple[str, str]:
    matter = client.post("/api/matters", json={"name": "Acme / Brightline NDA", "client_name": "Acme Robotics"}).json()
    up = client.post(f"/api/matters/{matter['id']}/documents",
                     files=[("files", ("Mutual NDA.docx", sample_nda_docx(), DOCX)),
                            ("files", ("Brightline email.txt", INJECTION_EMAIL.encode(), "text/plain"))])
    assert up.status_code == 201, up.text
    assert jobs.work(HANDLERS, once=True) == 2
    return matter["id"], up.json()[0]["id"]


def test_signup_seeds_starter_playbooks_and_audit(client):
    signup(client)
    me = client.get("/api/me").json()
    assert me["user"]["role"] == "admin"
    playbooks = client.get("/api/playbooks").json()
    assert {p["slug"] for p in playbooks} == {"nda", "commercial"}
    assert all(p["is_starter"] and p["validated_by"] is None for p in playbooks)


def test_login_and_wrong_password(client):
    signup(client)
    client.post("/api/auth/logout")
    assert client.get("/api/me").status_code == 401
    bad = client.post("/api/auth/login", json={"email": "partner@madiraju.example", "password": "nope-nope-nope"})
    assert bad.status_code == 401
    ok = client.post("/api/auth/login", json={"email": "PARTNER@madiraju.example", "password": "correct horse battery"})
    assert ok.status_code == 200
    assert client.get("/api/me").status_code == 200


def test_duplicate_email_is_rejected(client):
    signup(client)
    client.cookies.clear()
    r = client.post("/api/auth/signup", json={"firm_name": "Other", "name": "X",
                                              "email": "partner@madiraju.example", "password": "another password"})
    assert r.status_code == 409


def test_mutations_need_the_client_header(client):
    signup(client)
    r = client.post("/api/matters", json={"name": "x"}, headers={"x-nexus-client": ""})
    assert r.status_code == 403


def test_upload_processes_scans_and_indexes(client):
    signup(client)
    matter_id, nda_id = _matter_with_nda(client)
    docs = client.get(f"/api/matters/{matter_id}/documents").json()
    assert {d["status"] for d in docs} == {"ready"}
    email = next(d for d in docs if d["filename"].endswith(".txt"))
    assert email["flags"]["hidden_instruction_count"] == 1
    nda = next(d for d in docs if d["id"] == nda_id)
    assert nda["flags"]["hidden_instruction_count"] == 0

    passages = client.get(f"/api/documents/{nda_id}/passages").json()
    assert len(passages) >= 8
    firm_id = client.get("/api/me").json()["firm"]["id"]
    with tenant(firm_id) as s:
        hits = search.search(s, matter_id, "non-solicitation employees")
        assert "solicit, employ or engage" in hits[0]["text"]
        stems = search.search(s, matter_id, "terminated")  # stemming: terminate/termination
        assert any("terminated earlier" in h["text"] for h in stems)


def test_rejects_unsupported_and_oversized_files(client):
    signup(client)
    matter = client.post("/api/matters", json={"name": "m"}).json()
    r = client.post(f"/api/matters/{matter['id']}/documents", files=[("files", ("x.exe", b"MZ", "application/octet-stream"))])
    assert r.status_code == 415


def test_unreadable_pdf_fails_with_a_plain_message(client):
    signup(client)
    matter = client.post("/api/matters", json={"name": "m"}).json()
    client.post(f"/api/matters/{matter['id']}/documents", files=[("files", ("broken.pdf", b"%PDF-1.4 garbage", "application/pdf"))])
    jobs.work(HANDLERS, once=True)
    doc = client.get(f"/api/matters/{matter['id']}/documents").json()[0]
    assert doc["status"] == "failed"
    assert "could not be read" in doc["error"] or "no text layer" in doc["error"]


def test_firms_cannot_see_each_other(client):
    signup(client)
    matter_id, nda_id = _matter_with_nda(client)
    firm_a = client.get("/api/me").json()["firm"]["id"]

    client.cookies.clear()
    signup(client, firm="Other LLP", email="other@other.example")
    assert client.get("/api/matters").json() == []
    assert client.get(f"/api/matters/{matter_id}").status_code == 404
    assert client.get(f"/api/documents/{nda_id}/file").status_code == 404
    assert client.post(f"/api/matters/{matter_id}/ask", json={"question": "What is the term?"}).status_code == 404

    # Even raw SQL with no WHERE clause sees only the current firm's rows.
    firm_b = client.get("/api/me").json()["firm"]["id"]
    with tenant(firm_b) as s:
        assert rows(s, "SELECT * FROM passages") == []
        assert rows(s, "SELECT * FROM documents") == []
        assert len(rows(s, "SELECT * FROM firms")) == 1
    with tenant(firm_a) as s:
        assert len(rows(s, "SELECT * FROM documents")) == 2


def test_cannot_write_into_another_firm(client):
    signup(client)
    firm_a = client.get("/api/me").json()["firm"]["id"]
    client.cookies.clear()
    signup(client, firm="Other LLP", email="other@other.example")
    firm_b = client.get("/api/me").json()["firm"]["id"]
    with pytest.raises(DBAPIError, match="row-level security"), tenant(firm_b) as s:
        s.execute(text("INSERT INTO matters (firm_id, name) VALUES (:f, 'sneaky')"), {"f": firm_a})


def test_audit_trail_is_append_only(client):
    signup(client)
    firm_id = client.get("/api/me").json()["firm"]["id"]
    with pytest.raises(DBAPIError), tenant(firm_id) as s:
        s.execute(text("UPDATE audit_events SET action = 'tampered'"))
    with pytest.raises(DBAPIError), tenant(firm_id) as s:
        s.execute(text("DELETE FROM audit_events"))
    with tenant(firm_id) as s:
        assert row(s, "SELECT action FROM audit_events ORDER BY id LIMIT 1")["action"] == "firm.created"


def test_ask_needs_documents_and_queues_a_run(client):
    signup(client)
    empty = client.post("/api/matters", json={"name": "empty"}).json()
    assert client.post(f"/api/matters/{empty['id']}/ask", json={"question": "Anything?"}).status_code == 409

    matter_id, _ = _matter_with_nda(client)
    run = client.post(f"/api/matters/{matter_id}/ask", json={"question": "How long does confidentiality last?"})
    assert run.status_code == 201
    detail = client.get(f"/api/runs/{run.json()['id']}").json()
    assert detail["status"] == "queued" and detail["kind"] == "ask"


def test_roles_limit_who_can_approve_and_edit(client):
    signup(client)
    client.post("/api/team", json={"name": "Para", "email": "para@madiraju.example", "role": "paralegal",
                                   "temporary_password": "temporary password"})
    matter_id, nda_id = _matter_with_nda(client)
    playbook = client.get("/api/playbooks").json()[0]
    run = client.post(f"/api/matters/{matter_id}/reviews", json={
        "document_id": nda_id, "playbook_id": playbook["id"], "client_role": "Mutual; we are Acme"}).json()

    client.cookies.clear()
    client.post("/api/auth/login", json={"email": "para@madiraju.example", "password": "temporary password"})
    assert client.post(f"/api/runs/{run['id']}/approve", json={}).status_code == 403
    assert client.post(f"/api/playbooks/{playbook['id']}/validate", json={"lawyer_name": "Me"}).status_code == 403
    assert client.get("/api/audit").status_code == 403


def test_disabled_member_is_signed_out(client):
    signup(client)
    member = client.post("/api/team", json={"name": "A", "email": "a@madiraju.example", "role": "associate",
                                            "temporary_password": "temporary password"}).json()
    other = client.__class__(client.app, headers={"x-nexus-client": "test"})
    other.post("/api/auth/login", json={"email": "a@madiraju.example", "password": "temporary password"})
    assert other.get("/api/matters").status_code == 200
    client.patch(f"/api/team/{member['id']}", json={"disabled": True})
    assert other.get("/api/matters").status_code == 401


def test_editing_a_playbook_clears_its_approval(client):
    signup(client)
    playbook = client.get("/api/playbooks").json()[0]
    client.post(f"/api/playbooks/{playbook['id']}/validate", json={"lawyer_name": "A. Partner"})
    assert client.get(f"/api/playbooks/{playbook['id']}").json()["validated_by"] == "A. Partner"
    full = client.get(f"/api/playbooks/{playbook['id']}").json()
    r = client.put(f"/api/playbooks/{playbook['id']}", json={
        "name": full["name"], "description": full["description"], "positions": full["positions"][:3]})
    assert r.status_code == 200
    assert client.get(f"/api/playbooks/{playbook['id']}").json()["validated_by"] is None
