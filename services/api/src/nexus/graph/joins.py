"""Suggesting joins, within one connection and across connections.

Three kinds of evidence, strongest first:
  * a foreign key declared in the warehouse;
  * names: `orders.customer_id` and a table called `customers` with an `id`
    (or `customer_id`) column of a compatible type;
  * data: a sample of the referencing column's values is looked up in the
    referenced column, and the referenced column is checked to be a key.

Name matches are only proposed when the data agrees. Nothing is approved
here: every suggestion waits for a steward. A suggestion that was rejected is
never proposed again.
"""

import json
import logging
import re
from contextlib import ExitStack

from nexus import connections
from nexus.connectors import ConnectorError
from nexus.db import rows, scalar, tenant
from nexus.graph.collect import tables_with_columns

log = logging.getLogger("nexus.joins")

JOB_KIND = "suggest_joins"
SAMPLE = 500
MIN_OVERLAP = 0.5
MAX_CANDIDATES = 300

_ID = re.compile(r"^(?P<base>[a-z0-9_]+?)_?(id|key|code|ref|no|number)$")
_PREFIXES = ("dim_", "fct_", "fact_", "stg_", "raw_", "src_")
_NUMERIC = {"integer", "numeric"}
_IDISH = {"integer", "numeric", "string"}


def singular(word: str) -> str:
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith(("ses", "xes")):
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def table_base(name: str) -> str:
    name = name.lower()
    for prefix in _PREFIXES:
        if name.startswith(prefix):
            name = name[len(prefix):]
    return singular(name)


def compatible(a: str, b: str) -> bool:
    return a == b or (a in _IDISH and b in _IDISH)


def _candidates(tables: list[dict]) -> list[dict]:
    by_key = {t["key"]: t for t in tables}
    by_base: dict[str, list[dict]] = {}
    for t in tables:
        by_base.setdefault(table_base(t["attrs"]["table"]), []).append(t)
    out: dict[tuple, dict] = {}

    def add(left_t, left_c, right_t, right_c, evidence):
        if left_t["id"] == right_t["id"]:
            return
        pair = (str(left_c["id"]), str(right_c["id"]))
        if pair in out:
            out[pair]["evidence"].update(evidence)
        else:
            out[pair] = {"left_table": left_t, "left_column": left_c, "right_table": right_t,
                         "right_column": right_c, "evidence": dict(evidence)}

    for t in tables:
        for c in t["columns"]:
            ref = c["attrs"].get("references")
            if ref and ref["table"] in by_key:
                target = by_key[ref["table"]]
                match = next((x for x in target["columns"] if x["attrs"]["column"].lower() == ref["column"].lower()), None)
                if match:
                    add(t, c, target, match, {"declared": True})
            name = c["attrs"]["column"].lower()
            m = _ID.match(name)
            if not m or name == "id":
                continue
            base = singular(m.group("base").rstrip("_"))
            for target in by_base.get(base, []):
                wanted = ("id", name, f"{base}_id", f"{base}id", f"{base}_key")
                match = next((x for x in target["columns"] if x["attrs"]["column"].lower() in wanted), None)
                if match and compatible(c["attrs"]["data_type"], match["attrs"]["data_type"]):
                    add(t, c, target, match, {"name_match": f"{name} → {target['attrs']['table']}"})
    return list(out.values())[:MAX_CANDIDATES]


def suggest_joins(workspace_id: str, payload: dict | None = None) -> int:
    """Propose joins for the workspace. Returns how many new suggestions were made."""
    with tenant(workspace_id) as s:
        tables = tables_with_columns(s)
        conns = {str(c["id"]): c for c in rows(s, "SELECT * FROM connections")}
        known = {r["key"]: r["status"] for r in rows(s, "SELECT key, status FROM kg_items WHERE kind = 'join'")}
    candidates = _candidates(tables)

    proposals = []
    with ExitStack() as stack:
        open_whs: dict[str, object] = {}

        def warehouse(connection_id: str):
            if connection_id not in open_whs:
                try:
                    open_whs[connection_id] = stack.enter_context(
                        connections.open_warehouse(workspace_id, conns[connection_id]))
                except (ConnectorError, KeyError) as exc:
                    log.warning("joins: cannot open connection %s: %s", connection_id, exc)
                    open_whs[connection_id] = None
            return open_whs[connection_id]

        for cand in candidates:
            lt, lc, rt, rc = cand["left_table"], cand["left_column"], cand["right_table"], cand["right_column"]
            key = f"{lc['key']}={rc['key']}"
            if known.get(key) in ("approved", "rejected", "deprecated"):
                continue
            evidence = cand["evidence"]
            left_wh, right_wh = warehouse(str(lt["connection_id"])), warehouse(str(rt["connection_id"]))
            if left_wh is not None and right_wh is not None:
                try:
                    la, ra = lt["attrs"], rt["attrs"]
                    values = left_wh.sample(la["database"], la["schema"], la["table"], lc["attrs"]["column"], SAMPLE)
                    numeric = rc["attrs"]["data_type"] in _NUMERIC and all(
                        isinstance(v, int | float) or str(v).lstrip("-").isdigit() for v in values)
                    matched = right_wh.count_matching(ra["database"], ra["schema"], ra["table"],
                                                      rc["attrs"]["column"], values, numeric) if values else 0
                    evidence["sampled"] = len(values)
                    evidence["overlap"] = round(matched / len(values), 3) if values else 0.0
                    evidence["right_key_ratio"] = round(right_wh.distinct_ratio(
                        ra["database"], ra["schema"], ra["table"], rc["attrs"]["column"]), 3)
                except ConnectorError as exc:
                    evidence["data_check_error"] = str(exc)
            overlap = evidence.get("overlap")
            if not evidence.get("declared") and (overlap is None or overlap < MIN_OVERLAP):
                continue
            key_ratio = evidence.get("right_key_ratio") or 0
            confidence = 0.95 if evidence.get("declared") else round(
                0.2 + 0.5 * (overlap or 0) + (0.25 if key_ratio >= 0.98 else 0), 2)
            proposals.append({
                "key": key, "left_table": lt, "right_table": rt, "left_column": lc, "right_column": rc,
                "evidence": evidence, "confidence": min(confidence, 0.95),
                "cardinality": "many_to_one" if key_ratio >= 0.98 else "unknown",
                "origin": "discovered" if evidence.get("declared") else "suggested",
            })

    made = 0
    with tenant(workspace_id) as s:
        for p in proposals:
            lt, rt, lc, rc = p["left_table"], p["right_table"], p["left_column"], p["right_column"]
            attrs = {"left_table_id": str(lt["id"]), "right_table_id": str(rt["id"]),
                     "left_column_id": str(lc["id"]), "right_column_id": str(rc["id"]),
                     "left_column": lc["attrs"]["column"], "right_column": rc["attrs"]["column"],
                     "cross_source": str(lt["connection_id"]) != str(rt["connection_id"]),
                     "confidence": p["confidence"], "cardinality": p["cardinality"], "evidence": p["evidence"]}
            name = f"{lt['name']}.{lc['attrs']['column']} → {rt['name']}.{rc['attrs']['column']}"
            inserted = scalar(s, """INSERT INTO kg_items (workspace_id, kind, key, connection_id, parent_id, name,
                                                          attrs, origin)
                                    VALUES (:w, 'join', :k, :c, :p, :n, CAST(:a AS jsonb), :o)
                                    ON CONFLICT (workspace_id, kind, key) DO UPDATE
                                      SET attrs = EXCLUDED.attrs, updated_at = now()
                                      WHERE kg_items.status = 'proposed'
                                    RETURNING (xmax = 0)""",
                              w=workspace_id, k=p["key"], c=lt["connection_id"], p=lt["id"], n=name,
                              a=json.dumps(attrs, default=str), o=p["origin"])
            made += int(bool(inserted))
    return made
