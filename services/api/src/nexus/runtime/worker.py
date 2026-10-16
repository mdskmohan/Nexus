"""The background worker: executes runs from the job queue."""

import logging

from nexus import jobs
from nexus.runtime.engine import HANDLERS, close_orphaned_runs

log = logging.getLogger("nexus.worker")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    closed = close_orphaned_runs()
    log.info("worker started%s", f"; closed {closed} interrupted run(s)" if closed else "")
    jobs.work(HANDLERS)
