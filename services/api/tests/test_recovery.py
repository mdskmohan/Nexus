"""A worker can die mid-task. Tasks must never be left 'working' forever, and
paid AI work is not silently repeated."""

from nexus import jobs
from nexus.db import row, scalar, tenant, unscoped
from nexus.tasks import HANDLERS, INTERRUPTED, close_orphaned_runs
from tests.conftest import add_local_model, signup
from tests.test_platform import _matter_with_nda


def _start_ask(client) -> tuple[str, str]:
    signup(client)
    matter_id, _ = _matter_with_nda(client)
    add_local_model(client)
    run = client.post(f"/api/matters/{matter_id}/ask", json={"question": "What is the term?"}).json()
    return client.get("/api/me").json()["firm"]["id"], run["id"]


def test_job_of_a_dead_worker_is_reclaimed_and_its_task_marked_interrupted(client):
    firm, run_id = _start_ask(client)
    # Simulate: a worker (pid that cannot exist) claimed the job and began the run, then died.
    import socket
    with unscoped() as s:
        scalar(s, """UPDATE jobs SET status = 'running', attempts = 1, locked_at = now(), locked_by = :w
                     WHERE kind = 'run_agent' RETURNING 1""", w=f"{socket.gethostname()}:999999")
    with tenant(firm) as s:
        scalar(s, "UPDATE runs SET status = 'running' WHERE id = :r RETURNING 1", r=run_id)
    assert jobs.work(HANDLERS, once=True) == 1  # reclaimed immediately, not after 30 minutes
    detail = client.get(f"/api/runs/{run_id}").json()
    assert detail["status"] == "failed" and detail["error"] == INTERRUPTED


def test_orphaned_running_task_is_closed_at_worker_start(client):
    firm, run_id = _start_ask(client)
    with unscoped() as s:
        scalar(s, "UPDATE jobs SET status = 'done' WHERE kind = 'run_agent' RETURNING 1")
    with tenant(firm) as s:
        scalar(s, "UPDATE runs SET status = 'running' WHERE id = :r RETURNING 1", r=run_id)
    assert close_orphaned_runs() == 1
    with tenant(firm) as s:
        assert row(s, "SELECT status, error FROM runs WHERE id = :r", r=run_id) == {
            "status": "failed", "error": INTERRUPTED}
    assert close_orphaned_runs() == 0


def test_stopping_a_task(client):
    firm, run_id = _start_ask(client)
    assert client.post(f"/api/runs/{run_id}/cancel").json() == {"ok": True}
    detail = client.get(f"/api/runs/{run_id}").json()
    assert detail["status"] == "cancelled" and detail["error"].startswith("Stopped by")
    assert jobs.work(HANDLERS, once=True) == 1  # the queued job sees it was stopped and does nothing
    assert client.get(f"/api/runs/{run_id}").json()["status"] == "cancelled"
    assert client.post(f"/api/runs/{run_id}/cancel").status_code == 409
