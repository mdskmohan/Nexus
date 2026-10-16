"""Collecting metadata from a connection into the knowledge graph.

Everything read from a warehouse arrives as a proposal: tables and columns
are `discovered` items with status 'proposed' until a steward approves them.
Collecting again updates what changed, marks what disappeared, and never
changes a review decision. Declared foreign keys are kept on the column so
join suggestion can use them.
"""

import json
import logging

from nexus import connections, jobs
from nexus.connectors import ConnectorError
from nexus.db import row, rows, scalar, tenant

log = logging.getLogger("nexus.collect")

JOB_KIND = "collect"


def table_key(connection_id: str, table_key: str) -> str:
    return f"{connection_id}:{table_key}"


def collect(workspace_id: str, payload: dict) -> None:
    connection_id = payload["connection_id"]
    with tenant(workspace_id) as s:
        conn = row(s, "SELECT * FROM connections WHERE id = :c", c=connection_id)
        if conn is None:
            return
        scalar(s, "UPDATE connections SET collect_status = 'running', collect_msg = NULL WHERE id = :c RETURNING id",
               c=connection_id)
    try:
        with connections.open_warehouse(workspace_id, conn) as wh:
            tables = wh.tables()
            try:
                foreign_keys = wh.foreign_keys()
            except ConnectorError as exc:  # keys are a bonus; their absence must not fail collection
                log.warning("connection %s: foreign keys unavailable: %s", connection_id, exc)
                foreign_keys = []
    except ConnectorError as exc:
        with tenant(workspace_id) as s:
            scalar(s, """UPDATE connections SET collect_status = 'failed', collect_msg = :m
                         WHERE id = :c RETURNING id""", m=f"Could not read the warehouse: {exc}", c=connection_id)
        return

    references = {(fk.table, fk.column.lower()): (fk.ref_table, fk.ref_column) for fk in foreign_keys}
    with tenant(workspace_id) as s:
        new_tables = 0
        seen: list[str] = []
        for t in tables:
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
        # With new metadata in place, look for joins (within and across connections).
        jobs.enqueue(s, workspace_id, "suggest_joins", {"connection_id": connection_id}, max_attempts=1)


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
