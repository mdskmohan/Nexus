"""Runs: every read of a connection, with progress, counts, a live log, cancel, retry and failure reasons.

Uses the demo Postgres warehouses, so it runs wherever the rest of the suite does.
"""

from nexus import demo, jobs
from nexus.db import scalar, tenant, unscoped
from nexus.graph.collect import INTERRUPTED, close_orphaned_runs, explain
from nexus.runtime.worker import HANDLERS
from tests.conftest import signup


def _connect(client, label="Sales", database="nexus_demo_sales", **override) -> str:
    values = {**demo.connection_values(database), **override}
    r = client.post("/api/connections", json={"kind": "postgres", "label": label, "values": values})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _start(client, conn_id) -> str:
    r = client.post(f"/api/connections/{conn_id}/collect")
    assert r.status_code == 200, r.text
    return r.json()["run_id"]


def _logs(client, run_id) -> list[str]:
    return [line["message"] for line in client.get(f"/api/connections/runs/{run_id}/logs").json()]


def test_a_run_records_its_phases_counts_and_log(client):
    signup(client)
    conn_id = _connect(client)
    run_id = _start(client, conn_id)
    queued = client.get(f"/api/connections/runs/{run_id}").json()
    assert queued["status"] == "queued" and queued["trigger"] == "manual" and queued["requested_by_name"]
    assert client.post(f"/api/connections/{conn_id}/collect").status_code == 409  # one at a time

    jobs.work(HANDLERS, once=True)
    run = client.get(f"/api/connections/runs/{run_id}").json()
    assert run["status"] == "succeeded" and run["phase"] == "done" and run["progress"] == 100
    assert run["started_at"] and run["finished_at"] and run["error"] is None
    stats = run["stats"]
    assert stats["tables"] == 4 and stats["views"] == 0 and stats["columns"] == 16 and stats["schemas"] == 1
    assert stats["new_tables"] == 4 and stats["known_tables"] == 0 and stats["removed_tables"] == 0
    assert stats["foreign_keys"] >= 1 and "joins_suggested" in stats and stats["seconds"] >= 0

    logs = _logs(client, run_id)
    assert logs[0] == "Queued. Waiting for a worker." and logs[1].startswith("Started reading Sales")
    assert any(m.startswith("Connected in") for m in logs)
    assert any(m.startswith("Found 4 tables, 0 views and 16 columns") for m in logs)
    assert any(m.startswith("Saved to the knowledge graph for review: 4 new tables") for m in logs)
    assert logs[-1].startswith("Finished in")
    assert client.get(f"/api/connections/runs/{run_id}/logs", params={"after": 10**9}).json() == []

    conn = client.get(f"/api/connections/{conn_id}").json()
    assert conn["collect_status"] == "done" and conn["last_run"]["id"] == run_id
    assert conn["last_success"]["stats"]["tables"] == 4
    assert [r["id"] for r in client.get("/api/connections/runs", params={"connection_id": conn_id}).json()] == [run_id]
    assert client.get("/api/connections/runs", params={"status": "failed"}).json() == []
    assert client.get("/api/connections/runs/summary").json() == {
        "active": 0, "succeeded_24h": 1, "failed_24h": 0, "total": 1}

    # Reading again finds nothing new and says so.
    second = _start(client, conn_id)
    jobs.work(HANDLERS, once=True)
    again = client.get(f"/api/connections/runs/{second}").json()["stats"]
    assert again["new_tables"] == 0 and again["known_tables"] == 4


def test_a_failure_is_explained(client):
    signup(client)
    conn_id = _connect(client, "Wrong password", password="not-the-password")
    run_id = _start(client, conn_id)
    jobs.work(HANDLERS, once=True)
    run = client.get(f"/api/connections/runs/{run_id}").json()
    assert run["status"] == "failed" and run["error_kind"] == "auth"
    assert "password authentication failed" in run["error"] and "not-the-password" not in run["error"]
    assert run["hint"].startswith("Check the user and the password")
    logs = client.get(f"/api/connections/runs/{run_id}/logs").json()
    assert [line["level"] for line in logs][-2:] == ["error", "info"]
    assert client.get("/api/connections").json()[0]["collect_status"] == "failed"
    assert client.get("/api/connections/runs/summary").json()["failed_24h"] == 1

    unreachable = _connect(client, "Unreachable", port="1")
    run_id = _start(client, unreachable)
    jobs.work(HANDLERS, once=True)
    assert client.get(f"/api/connections/runs/{run_id}").json()["error_kind"] == "network"


def test_retry_starts_a_new_run(client):
    signup(client)
    conn_id = _connect(client, password="not-the-password")
    run_id = _start(client, conn_id)
    assert client.post(f"/api/connections/runs/{run_id}/retry").status_code == 409  # not finished
    jobs.work(HANDLERS, once=True)
    retried = client.post(f"/api/connections/runs/{run_id}/retry")
    assert retried.status_code == 201
    new = client.get(f"/api/connections/runs/{retried.json()['run_id']}").json()
    assert new["trigger"] == "retry" and new["status"] == "queued"


def test_cancelling_a_queued_run(client):
    signup(client)
    conn_id = _connect(client)
    run_id = _start(client, conn_id)
    cancelled = client.post(f"/api/connections/runs/{run_id}/cancel").json()
    assert cancelled["status"] == "cancelled" and cancelled["finished_at"]
    jobs.work(HANDLERS, once=True)  # the job finds the run cancelled and does nothing
    assert client.get(f"/api/connections/runs/{run_id}").json()["status"] == "cancelled"
    assert client.get("/api/connections").json()[0]["collect_status"] == "never"
    assert client.get("/api/graph/items").json() == []
    assert client.post(f"/api/connections/{conn_id}/collect").status_code == 200  # free to run again


def test_cancelling_a_running_run_leaves_the_graph_unchanged(client):
    signup(client)
    conn_id = _connect(client)
    run_id = _start(client, conn_id)
    ws = client.get("/api/me").json()["workspace"]["id"]
    with tenant(ws) as s:  # as if a worker had picked it up
        scalar(s, "UPDATE collect_runs SET status = 'running' WHERE id = :r RETURNING id", r=run_id)
    assert client.post(f"/api/connections/runs/{run_id}/cancel").json()["cancel_requested"]
    jobs.work(HANDLERS, once=True)
    run = client.get(f"/api/connections/runs/{run_id}").json()
    assert run["status"] == "cancelled"
    assert _logs(client, run_id)[-1].startswith("Cancelled. Nothing from this run was saved")
    assert client.get("/api/graph/items").json() == []


def test_the_live_stream_sends_the_log_and_the_run(client):
    signup(client)
    run_id = _start(client, _connect(client))
    jobs.work(HANDLERS, once=True)
    with client.stream("GET", f"/api/connections/runs/{run_id}/events") as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        body = r.read().decode()
    assert body.count("event: log") == len(_logs(client, run_id))
    assert "event: run" in body and body.rstrip().endswith('data: {"status": "succeeded"}')
    # Resuming after the last line seen sends no line twice.
    last = client.get(f"/api/connections/runs/{run_id}/logs").json()[-1]["id"]
    with client.stream("GET", f"/api/connections/runs/{run_id}/events",
                       headers={"Last-Event-ID": str(last)}) as r:
        assert "event: log" not in r.read().decode()
    assert client.get("/api/connections/runs/00000000-0000-0000-0000-000000000000/events").status_code == 404


def test_a_run_whose_worker_died_is_closed(client):
    signup(client)
    run_id = _start(client, _connect(client))
    with unscoped() as s:  # the job ended without the run finishing
        scalar(s, "UPDATE jobs SET status = 'failed' WHERE kind = 'collect' RETURNING id")
    assert close_orphaned_runs() == 1
    run = client.get(f"/api/connections/runs/{run_id}").json()
    assert run["status"] == "failed" and run["error"] == INTERRUPTED
    assert close_orphaned_runs() == 0


def test_only_people_who_may_see_connections_see_runs(client):
    signup(client)
    run_id = _start(client, _connect(client))
    client.post("/api/team", json={"name": "Ana", "email": "ana@acme.example", "role": "analyst",
                                   "temporary_password": "temporary password"})
    analyst = client.__class__(client.app, headers={"x-nexus-client": "test"})
    analyst.post("/api/auth/login", json={"email": "ana@acme.example", "password": "temporary password"})
    assert analyst.get("/api/connections/runs").status_code == 403
    assert analyst.post(f"/api/connections/runs/{run_id}/cancel").status_code == 403


def test_failure_reasons():
    assert explain("FATAL: password authentication failed for user x")[0] == "auth"
    assert explain("ORA-01017: invalid username/password")[0] == "auth"
    assert explain("connection to server at 10.0.0.1 port 5432 failed: Connection refused")[0] == "network"
    assert explain("ORA-00942: table or view does not exist")[0] == "permission"
    assert explain("Unknown database 'sales'")[0] == "not_found"
    assert explain("something else entirely")[0] == "warehouse"
