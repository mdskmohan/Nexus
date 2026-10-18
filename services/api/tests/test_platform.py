"""Workspaces, people, roles, isolation and the audit trail, through the HTTP API and against real Postgres."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from nexus.db import row, rows, tenant
from tests.conftest import signup


def _add(client, role: str, email: str) -> dict:
    r = client.post("/api/team", json={"name": role.title(), "email": email, "role": role,
                                       "temporary_password": "temporary password"})
    assert r.status_code == 201, r.text
    return r.json()


def _sign_in_as(client, email: str) -> None:
    client.cookies.clear()
    assert client.post("/api/auth/login", json={"email": email, "password": "temporary password"}).status_code == 200


def test_signup_creates_an_admin_and_an_audit_entry(client):
    signup(client)
    me = client.get("/api/me").json()
    assert me["user"]["role"] == "admin" and me["workspace"]["name"] == "Acme Analytics"
    assert "manage_people" in me["permissions"] and me["model_configured"] is False
    assert [e["action"] for e in client.get("/api/audit").json()] == ["workspace.created"]


def test_login_and_wrong_password(client):
    signup(client)
    client.post("/api/auth/logout")
    assert client.get("/api/me").status_code == 401
    bad = client.post("/api/auth/login", json={"email": "admin@acme.example", "password": "nope-nope-nope"})
    assert bad.status_code == 401
    ok = client.post("/api/auth/login", json={"email": "ADMIN@acme.example", "password": "correct horse battery"})
    assert ok.status_code == 200
    assert client.get("/api/me").status_code == 200


def test_duplicate_email_is_rejected(client):
    signup(client)
    client.cookies.clear()
    r = client.post("/api/auth/signup", json={"workspace_name": "Other", "name": "X",
                                              "email": "admin@acme.example", "password": "another password"})
    assert r.status_code == 409


def test_mutations_need_the_client_header(client):
    signup(client)
    r = client.post("/api/team", json={}, headers={"x-nexus-client": ""})
    assert r.status_code == 403


def test_roles_are_permissions_not_a_ladder(client):
    signup(client)
    _add(client, "steward", "steward@acme.example")
    _add(client, "developer", "dev@acme.example")
    _add(client, "viewer", "viewer@acme.example")

    _sign_in_as(client, "steward@acme.example")
    assert client.get("/api/audit").status_code == 200          # stewards see the audit trail
    assert client.get("/api/ai/providers").status_code == 403   # but do not manage AI models

    _sign_in_as(client, "dev@acme.example")
    assert client.get("/api/audit").status_code == 403          # developers build, they do not audit
    assert client.get("/api/runs").status_code == 200

    _sign_in_as(client, "viewer@acme.example")
    assert client.get("/api/runs").status_code == 403           # viewers only use published apps
    assert client.post("/api/team", json={"name": "x", "email": "x@acme.example", "role": "admin",
                                          "temporary_password": "temporary password"}).status_code == 403


def test_unknown_role_is_rejected(client):
    signup(client)
    r = client.post("/api/team", json={"name": "x", "email": "x@acme.example", "role": "partner",
                                       "temporary_password": "temporary password"})
    assert r.status_code == 422


def test_disabled_member_is_signed_out(client):
    signup(client)
    member = _add(client, "analyst", "a@acme.example")
    other = client.__class__(client.app, headers={"x-nexus-client": "test"})
    other.post("/api/auth/login", json={"email": "a@acme.example", "password": "temporary password"})
    assert other.get("/api/runs").status_code == 200
    client.patch(f"/api/team/{member['id']}", json={"disabled": True})
    assert other.get("/api/runs").status_code == 401


def test_workspaces_cannot_see_each_other(client):
    signup(client)
    _add(client, "analyst", "a@acme.example")
    ws_a = client.get("/api/me").json()["workspace"]["id"]
    client.cookies.clear()
    signup(client, workspace="Other Co", email="admin@other.example")
    assert [m["email"] for m in client.get("/api/team").json()] == ["admin@other.example"]
    ws_b = client.get("/api/me").json()["workspace"]["id"]
    # Even raw SQL with no WHERE clause sees only the current workspace's rows.
    with tenant(ws_b) as s:
        assert len(rows(s, "SELECT * FROM users")) == 1
        assert len(rows(s, "SELECT * FROM workspaces")) == 1
    with tenant(ws_a) as s:
        assert len(rows(s, "SELECT * FROM users")) == 2


def test_cannot_write_into_another_workspace(client):
    signup(client)
    ws_a = client.get("/api/me").json()["workspace"]["id"]
    client.cookies.clear()
    signup(client, workspace="Other Co", email="admin@other.example")
    ws_b = client.get("/api/me").json()["workspace"]["id"]
    with pytest.raises(DBAPIError, match="row-level security"), tenant(ws_b) as s:
        s.execute(text("INSERT INTO runs (workspace_id, kind, title) VALUES (:w, 'x', 'sneaky')"), {"w": ws_a})


def test_audit_trail_is_append_only(client):
    signup(client)
    ws = client.get("/api/me").json()["workspace"]["id"]
    with pytest.raises(DBAPIError), tenant(ws) as s:
        s.execute(text("UPDATE audit_events SET action = 'tampered'"))
    with pytest.raises(DBAPIError), tenant(ws) as s:
        s.execute(text("DELETE FROM audit_events"))
    with tenant(ws) as s:
        assert row(s, "SELECT action FROM audit_events ORDER BY id LIMIT 1")["action"] == "workspace.created"


def test_people_update_their_profile_and_password(client):
    signup(client)
    assert client.patch("/api/me", json={"name": "Ada Lovelace"}).status_code == 200
    assert client.get("/api/me").json()["user"]["name"] == "Ada Lovelace"
    wrong = client.patch("/api/me", json={"current_password": "not it", "new_password": "a brand new password"})
    assert wrong.status_code == 400 and wrong.json()["detail"] == "Your current password is not correct."
    assert client.patch("/api/me", json={"new_password": "a brand new password"}).status_code == 400
    assert client.patch("/api/me", json={"current_password": "correct horse battery",
                                         "new_password": "short"}).status_code == 422
    assert client.patch("/api/me", json={"current_password": "correct horse battery",
                                         "new_password": "a brand new password"}).status_code == 200
    client.post("/api/auth/logout")
    assert client.post("/api/auth/login", json={"email": "admin@acme.example",
                                                "password": "correct horse battery"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "admin@acme.example",
                                                "password": "a brand new password"}).status_code == 200


def test_only_admins_rename_the_workspace(client):
    signup(client)
    assert client.patch("/api/workspace", json={"name": "Acme Data"}).status_code == 200
    assert client.get("/api/me").json()["workspace"]["name"] == "Acme Data"
    client.post("/api/team", json={"name": "Vi", "email": "vi@acme.example", "role": "viewer",
                                   "temporary_password": "temporary password"})
    viewer = client.__class__(client.app, headers={"x-nexus-client": "test"})
    viewer.post("/api/auth/login", json={"email": "vi@acme.example", "password": "temporary password"})
    assert viewer.patch("/api/workspace", json={"name": "Mine now"}).status_code == 403
    assert viewer.patch("/api/me", json={"name": "Vi R"}).status_code == 200
