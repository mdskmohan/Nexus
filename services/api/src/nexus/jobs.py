"""A durable job queue on Postgres.

Jobs are claimed with FOR UPDATE SKIP LOCKED, so any number of workers can
run side by side without taking the same job. A job whose worker died is
picked up again once its lock goes stale.
"""

import json
import logging
import os
import socket
import time
from collections.abc import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from nexus.db import row, scalar, unscoped

log = logging.getLogger("nexus.jobs")
STALE_AFTER_MINUTES = 30

Handler = Callable[[str, dict], None]


def enqueue(session: Session, firm_id: UUID | str, kind: str, payload: dict,
            max_attempts: int = 3) -> int:
    return scalar(
        session,
        """INSERT INTO jobs (firm_id, kind, payload, max_attempts)
           VALUES (:firm, :kind, CAST(:payload AS jsonb), :max) RETURNING id""",
        firm=str(firm_id), kind=kind, payload=json.dumps(payload), max=max_attempts,
    )


def claim(worker: str) -> dict | None:
    with unscoped() as s:
        scalar(s, f"""UPDATE jobs SET status = 'queued', locked_at = NULL, locked_by = NULL
                      WHERE status = 'running'
                        AND locked_at < now() - interval '{STALE_AFTER_MINUTES} minutes'
                      RETURNING 1""")
        return row(
            s,
            """UPDATE jobs SET status = 'running', attempts = attempts + 1,
                      locked_at = now(), locked_by = :worker
               WHERE id = (SELECT id FROM jobs
                           WHERE status = 'queued' AND run_after <= now()
                           ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1)
               RETURNING id, firm_id, kind, payload, attempts, max_attempts""",
            worker=worker,
        )


def done(job_id: int) -> None:
    with unscoped() as s:
        scalar(s, "UPDATE jobs SET status = 'done', locked_at = NULL WHERE id = :id RETURNING 1", id=job_id)


def failed(job: dict, error: str) -> None:
    retry = job["attempts"] < job["max_attempts"]
    with unscoped() as s:
        scalar(
            s,
            """UPDATE jobs SET status = :status, last_error = :err, locked_at = NULL,
                      run_after = now() + make_interval(secs => :delay)
               WHERE id = :id RETURNING 1""",
            status="queued" if retry else "failed", err=error[:2000],
            delay=min(300, 5 * 2 ** job["attempts"]), id=job["id"],
        )


def work(handlers: dict[str, Handler], once: bool = False, idle_sleep: float = 1.0) -> int:
    """Process jobs until stopped (or until the queue is empty, if `once`)."""
    worker = f"{socket.gethostname()}:{os.getpid()}"
    processed = 0
    while True:
        job = claim(worker)
        if job is None:
            if once:
                return processed
            time.sleep(idle_sleep)
            continue
        handler = handlers.get(job["kind"])
        try:
            if handler is None:
                raise RuntimeError(f"no handler for job kind {job['kind']!r}")
            handler(str(job["firm_id"]), job["payload"])
            done(job["id"])
        except Exception as exc:  # the worker must survive any single job
            log.exception("job %s (%s) failed", job["id"], job["kind"])
            failed(job, f"{exc.__class__.__name__}: {exc}")
        processed += 1
