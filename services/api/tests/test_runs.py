"""Durable runs: pausing for a person, resuming, stopping, and recovering from a dead worker."""

import socket

from nexus import jobs
from nexus.db import row, scalar, tenant, unscoped
from nexus.runtime import engine
from nexus.runtime.engine import HANDLERS, INTERRUPTED, RunStopped, close_orphaned_runs
from tests.conftest import signup

PLANS_MADE = []


@engine.kind("test.approval")
def _needs_approval(ctx):
    # Stands in for paid work (an AI call, a warehouse query): must happen once, however often the run resumes.
    plan = ctx.checkpoint("plan", lambda: PLANS_MADE.append(ctx.run_id) or {"sql": "SELECT 1"})
    decision = ctx.ask("approve-plan", title="Approve the plan", shown={"plan": plan})
    if not decision.approved:
        raise RunStopped(f"The plan was rejected: {decision.note}")
    ctx.step("query", "Ran the approved plan.")
    return {"plan": plan, "approved_by": decision.decided_by}


@engine.kind("test.clarify")
def _needs_an_answer(ctx):
    decision = ctx.ask("which-revenue", kind="clarification", title="Which revenue: booked or recognised?",
                       permission="run_agents")
    return {"metric": decision.answer}


@engine.kind("test.boom")
def _breaks(ctx):
    raise ValueError("unexpected")


def _start(client, kind="test.approval") -> str:
    r = client.post("/api/runs", json={"kind": kind, "title": "Revenue by region"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _run(run_id, client) -> dict:
    return client.get(f"/api/runs/{run_id}").json()


def _add(client, role, email):
    assert client.post("/api/team", json={"name": role.title(), "email": email, "role": role,
                                          "temporary_password": "temporary password"}).status_code == 201


def _as(client, email):
    other = client.__class__(client.app, headers={"x-nexus-client": "test"})
    assert other.post("/api/auth/login", json={"email": email, "password": "temporary password"}).status_code == 200
    return other


def test_a_run_waits_for_approval_then_resumes_without_repeating_work(client):
    signup(client)
    run_id = _start(client)
    assert jobs.work(HANDLERS, once=True) == 1
    run = _run(run_id, client)
    assert run["status"] == "waiting"
    assert run["steps"][-1]["title"] == "Waiting for a person: Approve the plan"
    inbox = client.get("/api/requests").json()
    assert [q["title"] for q in inbox] == ["Approve the plan"] and inbox[0]["shown"] == {"plan": {"sql": "SELECT 1"}}

    assert client.post(f"/api/requests/{inbox[0]['id']}/decide", json={"decision": "approved"}).status_code == 200
    assert _run(run_id, client)["status"] == "queued"
    assert jobs.work(HANDLERS, once=True) == 1

    run = _run(run_id, client)
    me = client.get("/api/me").json()["user"]["id"]
    assert run["status"] == "succeeded" and run["output"] == {"plan": {"sql": "SELECT 1"}, "approved_by": me}
    assert PLANS_MADE.count(run_id) == 1  # the plan was made once, not again on resume
    assert [s["seq"] for s in run["steps"]] == list(range(1, len(run["steps"]) + 1))
    assert run["requests"][0]["status"] == "approved" and run["requests"][0]["decided_by_name"] == "Test Admin"
    actions = [e["action"] for e in client.get("/api/audit").json()]
    assert {"run.started", "run.asked_person", "request.approved", "run.succeeded"} <= set(actions)
    assert client.get("/api/requests").json() == []


def test_a_rejected_plan_stops_the_run_with_the_reason(client):
    signup(client)
    run_id = _start(client)
    jobs.work(HANDLERS, once=True)
    request_id = client.get("/api/requests").json()[0]["id"]
    client.post(f"/api/requests/{request_id}/decide", json={"decision": "rejected", "note": "Use net revenue."})
    jobs.work(HANDLERS, once=True)
    run = _run(run_id, client)
    assert run["status"] == "failed" and run["error"] == "The plan was rejected: Use net revenue."


def test_only_people_with_the_permission_can_decide(client):
    signup(client)
    _add(client, "analyst", "analyst@acme.example")
    analyst = _as(client, "analyst@acme.example")
    _start(analyst)
    jobs.work(HANDLERS, once=True)
    request_id = client.get("/api/requests").json()[0]["id"]
    assert analyst.get("/api/requests").json() == []  # not in their inbox
    r = analyst.post(f"/api/requests/{request_id}/decide", json={"decision": "approved"})
    assert r.status_code == 403
    assert client.post(f"/api/requests/{request_id}/decide", json={"decision": "approved"}).status_code == 200
    assert client.post(f"/api/requests/{request_id}/decide", json={"decision": "approved"}).status_code == 409


def test_a_clarification_needs_an_answer(client):
    signup(client)
    run_id = _start(client, "test.clarify")
    jobs.work(HANDLERS, once=True)
    request_id = client.get("/api/requests").json()[0]["id"]
    assert client.post(f"/api/requests/{request_id}/decide", json={"decision": "approved"}).status_code == 422
    assert client.post(f"/api/requests/{request_id}/decide",
                       json={"decision": "answered", "answer": "  "}).status_code == 422
    client.post(f"/api/requests/{request_id}/decide", json={"decision": "answered", "answer": "Recognised"})
    jobs.work(HANDLERS, once=True)
    assert _run(run_id, client)["output"] == {"metric": "Recognised"}


def test_stopping_a_waiting_run_closes_its_requests(client):
    signup(client)
    run_id = _start(client)
    jobs.work(HANDLERS, once=True)
    request_id = client.get("/api/requests").json()[0]["id"]
    assert client.post(f"/api/runs/{run_id}/cancel").json() == {"ok": True}
    run = _run(run_id, client)
    assert run["status"] == "cancelled" and run["error"] == "Stopped by Test Admin."
    assert run["requests"][0]["status"] == "cancelled"
    assert client.post(f"/api/requests/{request_id}/decide", json={"decision": "approved"}).status_code == 409
    assert client.post(f"/api/runs/{run_id}/cancel").status_code == 409


def test_a_queued_run_that_was_stopped_does_nothing(client):
    signup(client)
    run_id = _start(client)
    client.post(f"/api/runs/{run_id}/cancel")
    assert jobs.work(HANDLERS, once=True) == 1
    assert _run(run_id, client)["status"] == "cancelled"
    assert run_id not in PLANS_MADE


def test_only_the_starter_or_an_approver_can_stop_a_run(client):
    signup(client)
    _add(client, "analyst", "one@acme.example")
    _add(client, "analyst", "two@acme.example")
    run_id = _start(_as(client, "one@acme.example"))
    assert _as(client, "two@acme.example").post(f"/api/runs/{run_id}/cancel").status_code == 403
    assert client.post(f"/api/runs/{run_id}/cancel").status_code == 200


def test_unknown_kinds_are_rejected(client):
    signup(client)
    assert client.post("/api/runs", json={"kind": "nope", "title": "x"}).status_code == 422


def test_an_unexpected_error_fails_the_run_plainly(client):
    signup(client)
    run_id = _start(client, "test.boom")
    jobs.work(HANDLERS, once=True)
    run = _run(run_id, client)
    assert run["status"] == "failed" and run["error"].startswith("Something went wrong on our side")
    assert run["steps"][-1]["detail"]["error"] == "ValueError: unexpected"


def test_job_of_a_dead_worker_is_reclaimed_and_its_run_marked_interrupted(client):
    signup(client)
    run_id = _start(client)
    ws = client.get("/api/me").json()["workspace"]["id"]
    # Simulate: a worker (pid that cannot exist) claimed the job and began the run, then died.
    with unscoped() as s:
        scalar(s, """UPDATE jobs SET status = 'running', attempts = 1, locked_at = now(), locked_by = :w
                     RETURNING 1""", w=f"{socket.gethostname()}:999999")
    with tenant(ws) as s:
        scalar(s, "UPDATE runs SET status = 'running' WHERE id = :r RETURNING 1", r=run_id)
    assert jobs.work(HANDLERS, once=True) == 1  # reclaimed immediately, not after 30 minutes
    run = _run(run_id, client)
    assert run["status"] == "failed" and run["error"] == INTERRUPTED


def test_orphaned_running_run_is_closed_at_worker_start(client):
    signup(client)
    run_id = _start(client)
    ws = client.get("/api/me").json()["workspace"]["id"]
    with unscoped() as s:
        scalar(s, "UPDATE jobs SET status = 'done' RETURNING 1")
    with tenant(ws) as s:
        scalar(s, "UPDATE runs SET status = 'running' WHERE id = :r RETURNING 1", r=run_id)
    assert close_orphaned_runs() == 1
    with tenant(ws) as s:
        assert row(s, "SELECT status, error FROM runs WHERE id = :r", r=run_id) == {
            "status": "failed", "error": INTERRUPTED}
    assert close_orphaned_runs() == 0


def test_a_resumed_run_with_a_live_job_is_not_mistaken_for_an_orphan(client):
    signup(client)
    run_id = _start(client)
    jobs.work(HANDLERS, once=True)  # first job done; the run is waiting
    request_id = client.get("/api/requests").json()[0]["id"]
    client.post(f"/api/requests/{request_id}/decide", json={"decision": "approved"})
    ws = client.get("/api/me").json()["workspace"]["id"]
    with unscoped() as s:  # another worker has claimed the resume job and is running it
        scalar(s, "UPDATE jobs SET status = 'running' WHERE status = 'queued' RETURNING 1")
    with tenant(ws) as s:
        scalar(s, "UPDATE runs SET status = 'running' WHERE id = :r RETURNING 1", r=run_id)
    assert close_orphaned_runs() == 0
