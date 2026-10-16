"""The knowledge graph's system of record, its review, its versions, and its graph projection.

`kg_items` holds every table, column, join, entity and metric with its review
status. Only approved items reach agents. Each review that changes what is
approved creates a new graph version; an item belongs to version N when
approved_in <= N and (deprecated_in is null or deprecated_in > N).

Approved tables, joins, entities and metrics are also written to the
workspace's Apache AGE graph, in the same transaction, for traversal. Graph
elements carry `in_v` and `out_v` so a traversal can be pinned to a version.
"""

import json
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from nexus import audit
from nexus.db import row, rows, scalar

PROJECTED = ("table", "join", "entity", "metric")


class ReviewError(Exception):
    """A review that cannot be applied; the message is shown to the steward."""


# The graph (Apache AGE) ------------------------------------------------------

def cypher(session: Session, query: str, **params: object) -> list[dict]:
    """One Cypher statement against this workspace's graph (see migration 0002)."""
    return [r["r"] for r in rows(session, "SELECT r FROM kg_cypher(:q, CAST(:p AS jsonb)) AS r",
                                 q=query, p=json.dumps(params, default=str))]


def current_version(session: Session) -> int:
    return scalar(session, "SELECT coalesce(max(number), 0) FROM kg_versions")


def _new_version(session: Session, workspace_id: str, user_id: str | None, summary: dict) -> int:
    # One version number at a time per workspace.
    scalar(session, "SELECT pg_advisory_xact_lock(hashtext('kg_version:' || :w))", w=workspace_id)
    number = current_version(session) + 1
    scalar(session, """INSERT INTO kg_versions (workspace_id, number, summary, created_by)
                       VALUES (:w, :n, CAST(:s AS jsonb), :u) RETURNING id""",
           w=workspace_id, n=number, s=json.dumps(summary), u=user_id)
    return number


def _project_approved(session: Session, item: dict, version: int) -> None:
    a = item["attrs"]
    if item["kind"] == "table":
        cypher(session, """MERGE (t:Table {item_id: $id})
                           SET t.key = $key, t.name = $name, t.connection_id = $conn, t.in_v = $v
                           REMOVE t.out_v""",
               id=str(item["id"]), key=item["key"], name=item["name"], conn=str(item["connection_id"]), v=version)
    elif item["kind"] == "join":
        cypher(session, """MATCH (a:Table {item_id: $left}), (b:Table {item_id: $right})
                           CREATE (a)-[:JOINS {item_id: $id, left_column: $lc, right_column: $rc,
                                              cross_source: $cross, in_v: $v}]->(b)""",
               left=a["left_table_id"], right=a["right_table_id"], id=str(item["id"]), lc=a["left_column"],
               rc=a["right_column"], cross=bool(a.get("cross_source")), v=version)
    elif item["kind"] == "metric":
        cypher(session, """MATCH (t:Table {item_id: $table})
                           CREATE (:Metric {item_id: $id, name: $name, in_v: $v})-[:MEASURED_ON {in_v: $v}]->(t)""",
               table=a["table_id"], id=str(item["id"]), name=item["name"], v=version)
    elif item["kind"] == "entity":
        cypher(session, "CREATE (:Entity {item_id: $id, name: $name, in_v: $v})",
               id=str(item["id"]), name=item["name"], v=version)
        for table_id in a.get("table_ids", []):
            cypher(session, """MATCH (e:Entity {item_id: $id}), (t:Table {item_id: $table})
                               WHERE e.out_v IS NULL
                               CREATE (e)-[:REPRESENTED_BY {in_v: $v}]->(t)""",
                   id=str(item["id"]), table=table_id, v=version)


def _project_deprecated(session: Session, item: dict, version: int) -> None:
    item_id = str(item["id"])
    if item["kind"] == "join":
        cypher(session, "MATCH ()-[j:JOINS {item_id: $id}]->() WHERE j.out_v IS NULL SET j.out_v = $v",
               id=item_id, v=version)
    elif item["kind"] in ("table", "metric", "entity"):
        label = item["kind"].title()
        cypher(session, f"MATCH (n:{label} {{item_id: $id}}) WHERE n.out_v IS NULL SET n.out_v = $v",
               id=item_id, v=version)
        cypher(session, f"MATCH (n:{label} {{item_id: $id}})-[r]-() WHERE r.out_v IS NULL SET r.out_v = $v",
               id=item_id, v=version)


# Review --------------------------------------------------------------------

@dataclass
class _Batch:
    approve: dict[str, dict] = field(default_factory=dict)
    retire: dict[str, dict] = field(default_factory=dict)   # approved -> deprecated
    reject: dict[str, dict] = field(default_factory=dict)   # proposed -> rejected


def _items(session: Session, ids: list[str]) -> dict[str, dict]:
    if not ids:
        return {}
    found = rows(session, "SELECT * FROM kg_items WHERE id = ANY(CAST(:ids AS uuid[]))", ids=ids)
    return {str(i["id"]): i for i in found}


def _requires(item: dict) -> list[str]:
    """The table items an item depends on: they must be approved for it to be approved."""
    a = item["attrs"]
    if item["kind"] == "column":
        return [str(item["parent_id"])]
    if item["kind"] == "join":
        return [a["left_table_id"], a["right_table_id"]]
    if item["kind"] == "metric":
        return [a["table_id"]]
    if item["kind"] == "entity":
        return list(a.get("table_ids", []))
    return []


def _dependents(session: Session, table_ids: list[str]) -> list[dict]:
    """Items that stop making sense when these tables leave the graph."""
    if not table_ids:
        return []
    return rows(session, """SELECT * FROM kg_items
                            WHERE status IN ('proposed', 'approved') AND (
                                  parent_id = ANY(CAST(:t AS uuid[]))
                               OR attrs->>'left_table_id' = ANY(:t) OR attrs->>'right_table_id' = ANY(:t)
                               OR attrs->>'table_id' = ANY(:t)
                               OR EXISTS (SELECT 1 FROM jsonb_array_elements_text(
                                            coalesce(attrs->'table_ids', '[]'::jsonb)) x WHERE x = ANY(:t)))""",
                t=table_ids)


def review(session: Session, workspace_id: str, user_id: str, item_ids: list[str], decision: str,
           note: str | None = None) -> dict:
    """Approve or reject items. Returns what changed and the new graph version, if any."""
    if decision not in ("approve", "reject"):
        raise ReviewError("Decide approve or reject.")
    chosen = _items(session, list(dict.fromkeys(item_ids)))
    if len(chosen) != len(set(item_ids)):
        raise ReviewError("Some of these items no longer exist. Reload and try again.")
    batch = _Batch()

    if decision == "approve":
        for item_id, item in chosen.items():
            if item["status"] != "approved":
                batch.approve[item_id] = item
        # Approving a table brings its proposed columns with it.
        tables = [i for i, it in batch.approve.items() if it["kind"] == "table"]
        if tables:
            for col in rows(session, """SELECT * FROM kg_items WHERE kind = 'column' AND status = 'proposed'
                                        AND parent_id = ANY(CAST(:t AS uuid[]))""", t=tables):
                batch.approve.setdefault(str(col["id"]), col)
        needed = {d for it in batch.approve.values() for d in _requires(it)}
        approved_tables = {str(r["id"]) for r in rows(
            session, "SELECT id FROM kg_items WHERE id = ANY(CAST(:t AS uuid[])) AND status = 'approved'",
            t=list(needed))} if needed else set()
        for item in batch.approve.values():
            missing = [d for d in _requires(item) if d not in approved_tables and d not in batch.approve]
            if missing:
                names = ", ".join(r["name"] for r in rows(
                    session, "SELECT name FROM kg_items WHERE id = ANY(CAST(:t AS uuid[]))", t=missing))
                raise ReviewError(f"Approve {names} before {item['name']}.")
    else:
        for item_id, item in chosen.items():
            if item["status"] == "approved":
                batch.retire[item_id] = item
            elif item["status"] == "proposed":
                batch.reject[item_id] = item
        # A table leaving the graph takes its columns, joins, metrics and entity links with it.
        tables = [i for i, it in {**batch.retire, **batch.reject}.items() if it["kind"] == "table"]
        for dep in _dependents(session, tables):
            dep_id = str(dep["id"])
            if dep_id in batch.retire or dep_id in batch.reject:
                continue
            (batch.retire if dep["status"] == "approved" else batch.reject)[dep_id] = dep

    if not (batch.approve or batch.retire or batch.reject):
        return {"version": None, "approved": 0, "deprecated": 0, "rejected": 0}

    version = None
    if batch.approve or batch.retire:
        version = _new_version(session, workspace_id, user_id, {
            "approved": len(batch.approve), "deprecated": len(batch.retire), "note": note})
    for item_id in batch.approve:
        scalar(session, """UPDATE kg_items SET status = 'approved', approved_in = :v, deprecated_in = NULL,
                                  reviewed_by = :u, reviewed_at = now(), review_note = :n, updated_at = now()
                           WHERE id = :i RETURNING id""", v=version, u=user_id, n=note, i=item_id)
    for item_id in batch.retire:
        scalar(session, """UPDATE kg_items SET status = 'deprecated', deprecated_in = :v,
                                  reviewed_by = :u, reviewed_at = now(), review_note = :n, updated_at = now()
                           WHERE id = :i RETURNING id""", v=version, u=user_id, n=note, i=item_id)
    for item_id in batch.reject:
        scalar(session, """UPDATE kg_items SET status = 'rejected', reviewed_by = :u, reviewed_at = now(),
                                  review_note = :n, updated_at = now()
                           WHERE id = :i RETURNING id""", u=user_id, n=note, i=item_id)

    # Tables first, so joins, metrics and entities find their nodes.
    order = {"table": 0, "column": 1, "join": 2, "metric": 3, "entity": 4}
    for item in sorted(batch.approve.values(), key=lambda i: order[i["kind"]]):
        if item["kind"] in PROJECTED:
            _project_approved(session, item, version)
    for item in sorted(batch.retire.values(), key=lambda i: -order[i["kind"]]):
        if item["kind"] in PROJECTED:
            _project_deprecated(session, item, version)

    result = {"version": version, "approved": len(batch.approve), "deprecated": len(batch.retire),
              "rejected": len(batch.reject)}
    audit.record(session, workspace_id, user_id, f"graph.{decision}d", "kg_version", version,
                 items=[*batch.approve, *batch.retire, *batch.reject], note=note, **result)
    return result


# Reading -------------------------------------------------------------------

def join_paths(session: Session, from_table: str, to_table: str, version: int | None = None,
               max_hops: int = 4) -> list[dict]:
    """The shortest ways to join two approved tables, through approved joins, at a graph version."""
    v = version if version is not None else current_version(session)
    # AGE has no all() or list comprehensions over path elements, so each path's joins are
    # collected with their version range and filtered here. A join is only ever approved
    # while both its tables are, so checking the joins is enough.
    paths = cypher(session, f"""
        MATCH p = (a:Table {{item_id: $a}})-[:JOINS*1..{int(max_hops)}]-(b:Table {{item_id: $b}})
        UNWIND relationships(p) AS r
        WITH p, collect({{id: r.item_id, in_v: r.in_v, out_v: r.out_v}}) AS js
        RETURN {{hops: length(p), joins: js}}""", a=from_table, b=to_table)

    def live(j: dict) -> bool:
        return j["in_v"] <= v and (j.get("out_v") is None or j["out_v"] > v)

    found = sorted(({"hops": p["hops"], "joins": [j["id"] for j in p["joins"]]}
                    for p in paths if all(live(j) for j in p["joins"])), key=lambda p: p["hops"])[:5]
    join_ids = sorted({j for p in found for j in p["joins"]})
    joins = {str(j["id"]): j for j in rows(
        session, "SELECT id, name, attrs FROM kg_items WHERE id = ANY(CAST(:j AS uuid[]))", j=join_ids)} if join_ids else {}
    return [{"hops": p["hops"], "joins": [{"id": j, "name": joins[j]["name"],
                                            "cross_source": bool(joins[j]["attrs"].get("cross_source"))}
                                           for j in p["joins"]]} for p in found]


def item(session: Session, item_id: str) -> dict | None:
    return row(session, "SELECT * FROM kg_items WHERE id = CAST(:i AS uuid)", i=item_id)
