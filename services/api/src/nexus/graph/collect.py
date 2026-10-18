"""Collecting metadata from a connection into the knowledge graph, as a run.

Every read is a run (`collect_runs`): it is queued, then moves through five
phases (connect, discover, keys, graph, joins) while recording its progress,
what it found, and log lines people can follow live. A run can be cancelled;
a failed run keeps the reason and a hint about what to fix.

Everything read from a warehouse arrives as a proposal: tables and columns
are `discovered` items with status 'proposed' until a steward approves them.
Reading again updates what changed, marks what disappeared, and never changes
a review decision. Declared foreign keys are kept on the column so join
suggestion can use them. The graph is written in one transaction, so a run
that fails or is cancelled before it finishes writing leaves the graph as it
was.
"""

import json
import logging
import time

from sqlalchemy.orm import Session

from nexus import connections, jobs
from nexus.ai.secrets import SecretError
from nexus.connectors import KINDS, ConnectorError
from nexus.connectors.base import schema_allowed
from nexus.db import row, rows, scalar, tenant, unscoped

log = logging.getLogger("nexus.collect")

JOB_KIND = "collect"
ACTIVE = ("queued", "running")
FINISHED = ("succeeded", "failed", "cancelled")
# Where each phase starts on the progress bar; discovery takes most of a run.
PHASES = {"connect": 2, "discover": 8, "keys": 62, "graph": 70, "joins": 92, "done": 100}
INTERRUPTED = "The worker stopped before this run finished. Start it again."

# What a failure most likely means, matched against the driver's message (first match wins).
_EXPLAIN = (
    ("auth", ("password", "authentication", "login failed", "invalid credentials", "access denied for user",
              "ora-01017", "invalid_grant", "invalid token", "28000", "18456"),
     "Check the user and the password, key or token in this connection's settings."),
    ("network", ("timed out", "timeout", "could not connect", "connection refused", "unreachable",
                 "name or service not known", "nodename nor servname", "can't connect", "could not translate host",
                 "getaddrinfo", "no route to host", "network", "dpi-1080", "ora-12541", "adaptive server is unavailable"),
     "Check the host and port, and that the server accepts connections from Nexus (firewall, allow-list or VPN)."),
    ("permission", ("permission denied", "insufficient privilege", "ora-01031", "ora-00942", "not authorized",
                    "access denied", "does not have"),
     "Nexus signed in, but this user may not read the catalogue. Grant it read access to the schemas Nexus "
     "should read, then run again."),
    ("not_found", ("does not exist", "unknown database", "ora-12514", "cannot open database", "not found",
                   "invalid catalog", "no such"),
     "Check the name of the database, service or warehouse in this connection's settings."),
)


def explain(error: str) -> tuple[str, str]:
    """(kind, hint) for a failure message."""
    text = error.lower()
    for kind, needles, hint in _EXPLAIN:
        if any(n in text for n in needles):
            return kind, hint
    return "warehouse", "The error below comes from the warehouse; the log shows the step it happened in."


def n(count: int, noun: str, many: str | None = None) -> str:
    """'1 table', '3 tables'."""
    return f"{count} {noun if count == 1 else many or noun + 's'}"


def table_key(connection_id: str, table_key: str) -> str:
    return f"{connection_id}:{table_key}"


class Cancelled(Exception):
    """Someone asked for the run to stop."""


class RunLog:
    """Writes a run's progress and log lines, each in its own short transaction so they are visible at once."""

    def __init__(self, workspace_id: str, run_id: str):
        self.workspace_id, self.run_id = workspace_id, run_id

    def log(self, level: str, message: str, **data: object) -> None:
        with tenant(self.workspace_id) as s:
            scalar(s, """INSERT INTO collect_run_logs (workspace_id, run_id, level, message, data)
                         VALUES (:w, :r, :l, :m, CAST(:d AS jsonb)) RETURNING id""",
                   w=self.workspace_id, r=self.run_id, l=level, m=message[:4000],
                   d=json.dumps(data, default=str) if data else None)

    def update(self, phase: str | None = None, progress: float | None = None, **stats: object) -> None:
        """Record progress; raises Cancelled if someone asked the run to stop."""
        with tenant(self.workspace_id) as s:
            cancel = scalar(s, """UPDATE collect_runs
                                  SET phase = coalesce(:phase, phase),
                                      progress = greatest(progress, least(100, coalesce(:progress, progress))),
                                      stats = stats || CAST(:stats AS jsonb), updated_at = now()
                                  WHERE id = :r RETURNING cancel_requested""",
                            phase=phase, progress=progress, stats=json.dumps(stats), r=self.run_id)
        if cancel:
            raise Cancelled

    def finish(self, status: str, error: str | None = None) -> None:
        kind = explain(error)[0] if error else None
        with tenant(self.workspace_id) as s:
            scalar(s, """UPDATE collect_runs SET status = :st, error = :e, error_kind = :k, finished_at = now(),
                                updated_at = now(), phase = CASE WHEN :st = 'succeeded' THEN 'done' ELSE phase END,
                                progress = CASE WHEN :st = 'succeeded' THEN 100 ELSE progress END
                         WHERE id = :r RETURNING id""",
                   st=status, e=error[:4000] if error else None, k=kind, r=self.run_id)


# Starting and stopping runs ---------------------------------------------------------------

def start_run(s: Session, workspace_id: str, connection_id: str, trigger: str = "manual",
              user_id: str | None = None) -> str | None:
    """Queue a run for a connection. Returns its id, or None if one is already queued or running."""
    run_id = scalar(s, """INSERT INTO collect_runs (workspace_id, connection_id, trigger, requested_by)
                          VALUES (:w, :c, :t, :u)
                          ON CONFLICT (connection_id) WHERE status IN ('queued', 'running') DO NOTHING
                          RETURNING id""", w=workspace_id, c=connection_id, t=trigger, u=user_id)
    if run_id is None:
        return None
    scalar(s, """INSERT INTO collect_run_logs (workspace_id, run_id, level, message)
                 VALUES (:w, :r, 'info', 'Queued. Waiting for a worker.') RETURNING id""", w=workspace_id, r=run_id)
    scalar(s, "UPDATE connections SET collect_status = 'queued' WHERE id = :c RETURNING id", c=connection_id)
    jobs.enqueue(s, workspace_id, JOB_KIND, {"connection_id": str(connection_id), "run_id": str(run_id)},
                 max_attempts=1)
    return str(run_id)


def cancel_run(s: Session, run_id: str) -> str | None:
    """Cancel a queued run at once, or ask a running one to stop. Returns the run's status, or None."""
    run = row(s, "SELECT status, connection_id FROM collect_runs WHERE id = :r", r=run_id)
    if run is None:
        return None
    if run["status"] == "queued":
        scalar(s, """UPDATE collect_runs SET status = 'cancelled', finished_at = now(), updated_at = now()
                     WHERE id = :r RETURNING id""", r=run_id)
        scalar(s, """INSERT INTO collect_run_logs (workspace_id, run_id, level, message)
                     SELECT workspace_id, id, 'warning', 'Cancelled before it started.' FROM collect_runs
                     WHERE id = :r RETURNING id""", r=run_id)
        _settle_connection(s, run["connection_id"])
        return "cancelled"
    if run["status"] == "running":
        scalar(s, "UPDATE collect_runs SET cancel_requested = true, updated_at = now() WHERE id = :r RETURNING id",
               r=run_id)
        scalar(s, """INSERT INTO collect_run_logs (workspace_id, run_id, level, message)
                     SELECT workspace_id, id, 'warning', 'Cancel requested. Stopping at the next safe point.'
                     FROM collect_runs WHERE id = :r RETURNING id""", r=run_id)
    return run["status"]


def _settle_connection(s: Session, connection_id: object, message: str = "The last run was cancelled.") -> None:
    """After a run that did not finish, show the connection as it was before it."""
    scalar(s, """UPDATE connections SET collect_status = CASE WHEN collected_at IS NULL THEN 'never' ELSE 'done' END,
                        collect_msg = :m WHERE id = :c RETURNING id""", m=message, c=connection_id)


# The job ----------------------------------------------------------------------------------

def collect(workspace_id: str, payload: dict) -> None:
    connection_id = payload["connection_id"]
    run_id = payload.get("run_id")
    if run_id is None:  # queued before runs existed
        with tenant(workspace_id) as s:
            scalar(s, "UPDATE connections SET collect_status = 'never' WHERE id = :c RETURNING id", c=connection_id)
            run_id = start_run(s, workspace_id, connection_id, trigger="manual")
        return
    with tenant(workspace_id) as s:
        run = row(s, "SELECT status FROM collect_runs WHERE id = :r", r=run_id)
        conn = row(s, "SELECT * FROM connections WHERE id = :c", c=connection_id)
        if run is None or run["status"] in FINISHED or conn is None:
            return
        resumed = run["status"] == "running"
        scalar(s, """UPDATE collect_runs SET status = 'running', started_at = coalesce(started_at, now()),
                            phase = 'connect', progress = greatest(progress, :p), updated_at = now()
                     WHERE id = :r RETURNING id""", p=PHASES["connect"], r=run_id)
        scalar(s, "UPDATE connections SET collect_status = 'running', collect_msg = NULL WHERE id = :c RETURNING id",
               c=connection_id)

    run = RunLog(workspace_id, run_id)
    kind_name = KINDS[conn["kind"]].spec.name if conn["kind"] in KINDS else conn["kind"]
    run.log("warning" if resumed else "info",
            "Started again: the previous attempt stopped unexpectedly." if resumed
            else f"Started reading {conn['label']} ({kind_name}).")
    started = time.monotonic()
    saved = False
    try:
        saved = _read(run, workspace_id, conn, started)
        run.finish("succeeded")
    except Cancelled:
        run.log("warning", "Cancelled. Tables already saved stay in the knowledge graph; join suggestion was skipped."
                if saved else "Cancelled. Nothing from this run was saved; the knowledge graph is unchanged.")
        run.finish("cancelled")
        if not saved:
            with tenant(workspace_id) as s:
                _settle_connection(s, connection_id)
    except (ConnectorError, SecretError) as exc:
        message = str(exc) if isinstance(exc, ConnectorError) else "The saved credentials could not be decrypted."
        _fail(run, workspace_id, connection_id, message)
    except Exception as exc:  # the run must end in a known state whatever happens
        log.exception("run %s failed", run_id)
        _fail(run, workspace_id, connection_id, f"Nexus hit an unexpected error: {exc.__class__.__name__}: {exc}")


def _fail(run: RunLog, workspace_id: str, connection_id: str, message: str) -> None:
    run.log("error", message)
    run.log("info", explain(message)[1])
    run.finish("failed", message)
    with tenant(workspace_id) as s:
        scalar(s, """UPDATE connections SET collect_status = 'failed', collect_msg = :m
                     WHERE id = :c RETURNING id""", m=f"Could not read the warehouse: {message}", c=connection_id)


def _read(run: RunLog, workspace_id: str, conn: dict, started: float) -> bool:
    """The five phases. Returns whether the graph was written (it is by the time this returns)."""
    connection_id = str(conn["id"])
    with connections.open_warehouse(workspace_id, conn) as wh:
        run.log("success", f"Connected in {time.monotonic() - started:.1f}s.")
        run.update("discover", PHASES["discover"])

        span = PHASES["keys"] - PHASES["discover"]

        def on_schema(schema: str, done: int, total: int, found: int) -> None:
            run.log("info", f"Schema {schema}: {n(found, 'table or view', 'tables and views')} ({done} of {total}).", schema=schema)
            run.update(progress=PHASES["discover"] + span * done / max(total, 1), schemas_read=done,
                       schemas_total=total)

        wh.on_schema = on_schema
        # Connectors that read the whole catalogue in one query filter here instead.
        tables = [t for t in wh.tables() if schema_allowed(conn["config"], t.schema)]
        schemas = sorted({t.schema for t in tables})
        views = sum(t.kind == "view" for t in tables)
        columns = sum(len(t.columns) for t in tables)
        run.log("success" if tables else "warning",
                f"Found {n(len(tables) - views, 'table')}, {n(views, 'view')} and {n(columns, 'column')} in "
                f"{n(len(schemas), 'schema')}."
                if tables else "No tables are visible. Check the user's grants and this connection's schema filters.")
        run.update("keys", PHASES["keys"], schemas=len(schemas), tables=len(tables) - views, views=views,
                   columns=columns)

        try:
            foreign_keys = wh.foreign_keys()
            run.log("info", f"Read {n(len(foreign_keys), 'declared foreign key')}.")
        except ConnectorError as exc:  # keys are a bonus; their absence must not fail the run
            foreign_keys = []
            run.log("warning", f"Foreign keys could not be read, so joins will rest on names and data: {exc}")
        run.update("graph", PHASES["graph"], foreign_keys=len(foreign_keys))

    new_tables, gone = _write_graph(run, workspace_id, connection_id, tables, foreign_keys)
    run.log("success", f"Saved to the knowledge graph for review: {n(new_tables, 'new table')}, "
                       f"{len(tables) - new_tables} already known" + (f", {gone} no longer found." if gone else "."))
    run.update("joins", PHASES["joins"], new_tables=new_tables, known_tables=len(tables) - new_tables,
               removed_tables=gone)

    from nexus.graph.joins import suggest_joins  # joins reads what this module writes

    try:
        made = suggest_joins(workspace_id)
        run.log("success" if made else "info", f"Suggested {n(made, 'new join')}." if made else "No new joins to suggest.")
    except Exception as exc:  # suggestions are a bonus too
        log.exception("join suggestion failed for run %s", run.run_id)
        made = 0
        run.log("warning", f"Join suggestion failed; tables were still saved: {exc}")
    elapsed = time.monotonic() - started
    run.update("done", PHASES["done"], joins_suggested=made, seconds=round(elapsed, 1))
    run.log("success", f"Finished in {elapsed:.1f}s.")
    return True


def _write_graph(run: RunLog, workspace_id: str, connection_id: str, tables: list, foreign_keys: list) -> tuple[int, int]:
    references = {(fk.table, fk.column.lower()): (fk.ref_table, fk.ref_column) for fk in foreign_keys}
    every = max(1, len(tables) // 20)
    span = PHASES["joins"] - PHASES["graph"]
    with tenant(workspace_id) as s:
        new_tables = 0
        seen: list[str] = []
        for i, t in enumerate(tables, 1):
            key = table_key(connection_id, t.key)
            seen.append(key)
            attrs = {"database": t.database, "schema": t.schema, "table": t.name, "table_kind": t.kind,
                     "column_count": len(t.columns), "comment": t.comment}
            table = row(s, """INSERT INTO kg_items (workspace_id, kind, key, connection_id, name, attrs, origin)
                              VALUES (:w, 'table', :k, :c, :n, CAST(:a AS jsonb), 'discovered')
                              ON CONFLICT (workspace_id, kind, key) DO UPDATE
                                SET attrs = EXCLUDED.attrs, missing_since = NULL, updated_at = now()
                              RETURNING id, (xmax = 0) AS inserted""",
                        w=workspace_id, k=key, c=connection_id, n=f"{t.schema}.{t.name}", a=json.dumps(attrs))
            new_tables += int(table["inserted"])
            for col in t.columns:
                col_key = f"{key}.{col.name.lower()}"
                seen.append(col_key)
                ref = references.get((t.key, col.name.lower()))
                col_attrs = {"column": col.name, "data_type": col.data_type, "raw_type": col.raw_type,
                             "nullable": col.nullable, "ordinal": col.ordinal, "comment": col.comment,
                             "references": ({"table": table_key(connection_id, ref[0]), "column": ref[1]}
                                            if ref else None)}
                scalar(s, """INSERT INTO kg_items (workspace_id, kind, key, connection_id, parent_id, name, attrs, origin)
                             VALUES (:w, 'column', :k, :c, :p, :n, CAST(:a AS jsonb), 'discovered')
                             ON CONFLICT (workspace_id, kind, key) DO UPDATE
                               SET attrs = EXCLUDED.attrs, missing_since = NULL, updated_at = now()
                             RETURNING id""",
                       w=workspace_id, k=col_key, c=connection_id, p=table["id"], n=f"{t.name}.{col.name}",
                       a=json.dumps(col_attrs))
            if i % every == 0 or i == len(tables):
                # A cancel here rolls the whole write back.
                run.update(progress=PHASES["graph"] + span * i / len(tables), tables_saved=i)
        gone = scalar(s, """WITH gone AS (
                              UPDATE kg_items SET missing_since = coalesce(missing_since, now())
                              WHERE connection_id = :c AND origin = 'discovered' AND kind IN ('table', 'column')
                                AND NOT (key = ANY(:seen)) AND missing_since IS NULL
                              RETURNING kind)
                            SELECT count(*) FILTER (WHERE kind = 'table') FROM gone""", c=connection_id, seen=seen)
        message = (f"Read {len(tables)} tables and {sum(len(t.columns) for t in tables)} columns; "
                   f"{new_tables} new.") + (f" {gone} tables no longer found." if gone else "")
        scalar(s, """UPDATE connections SET collect_status = 'done', collected_at = now(), collect_msg = :m
                     WHERE id = :c RETURNING id""", m=message, c=connection_id)
    return new_tables, int(gone or 0)


def close_orphaned_runs() -> int:
    """Runs left queued or running although no job for them is live any more (the worker died, say)."""
    with unscoped() as s:
        ended = rows(s, f"""SELECT DISTINCT j.workspace_id, j.payload->>'run_id' AS run_id FROM jobs j
                            WHERE j.kind = '{JOB_KIND}' AND j.status IN ('done', 'failed')
                              AND j.payload ? 'run_id' AND j.created_at > now() - interval '7 days'
                              AND NOT EXISTS (SELECT 1 FROM jobs live
                                              WHERE live.kind = j.kind AND live.status IN ('queued', 'running')
                                                AND live.payload->>'run_id' = j.payload->>'run_id')""")
    closed = 0
    for j in ended:
        workspace_id = str(j["workspace_id"])
        with tenant(workspace_id) as s:
            stuck = row(s, "SELECT connection_id FROM collect_runs WHERE id = CAST(:r AS uuid) AND status IN "
                           "('queued', 'running')", r=j["run_id"])
        if stuck:
            _fail(RunLog(workspace_id, j["run_id"]), workspace_id, str(stuck["connection_id"]), INTERRUPTED)
            closed += 1
    return closed


def tables_with_columns(session, statuses=("proposed", "approved")) -> list[dict]:
    """Tables (not missing, not rejected) with their columns, for join suggestion."""
    tables = rows(session, """SELECT id, key, name, connection_id, attrs, status FROM kg_items
                              WHERE kind = 'table' AND status = ANY(:st) AND missing_since IS NULL""",
                  st=list(statuses))
    cols = rows(session, """SELECT id, key, parent_id, attrs, status FROM kg_items
                            WHERE kind = 'column' AND status = ANY(:st) AND missing_since IS NULL""",
                st=list(statuses))
    by_table: dict[str, list[dict]] = {}
    for c in cols:
        by_table.setdefault(str(c["parent_id"]), []).append(c)
    for t in tables:
        t["columns"] = by_table.get(str(t["id"]), [])
    return tables
