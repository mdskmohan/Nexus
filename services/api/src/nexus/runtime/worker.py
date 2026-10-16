"""The background worker: executes runs, reads warehouses, and suggests joins."""

import logging

from nexus import jobs
from nexus.graph import collect, joins
from nexus.runtime import engine
from nexus.runtime.engine import close_orphaned_runs

log = logging.getLogger("nexus.worker")

HANDLERS = {**engine.HANDLERS, collect.JOB_KIND: collect.collect, joins.JOB_KIND: joins.suggest_joins}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    closed = close_orphaned_runs()
    log.info("worker started%s", f"; closed {closed} interrupted run(s)" if closed else "")
    jobs.work(HANDLERS)
