"""Connections, metadata collection, join suggestion and the knowledge graph, against the two demo
warehouses (separate Postgres databases standing in for Snowflake and Databricks)."""

import psycopg
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from nexus import demo, jobs
from nexus.db import row, tenant
from nexus.runtime.worker import HANDLERS
from tests.conftest import signup


def _connect(client, label, database, **override):
    values = {**demo.connection_values(database), **override}
    r = client.post("/api/connections", json={"kind": "postgres", "label": label, "values": values})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _collect_both(client) -> tuple[str, str]:
    sales = _connect(client, "Sales", "nexus_demo_sales")
    crm = _connect(client, "CRM", "nexus_demo_crm")
    for c in (sales, crm):
        assert client.post(f"/api/connections/{c}/collect").status_code == 200
    jobs.work(HANDLERS, once=True)  # collect both, then suggest joins
    return sales, crm


def _items(client, **params) -> dict[str, dict]:
    return {i["name"]: i for i in client.get("/api/graph/items", params=params).json()}


def _add(client, role, email):
    assert client.post("/api/team", json={"name": role.title(), "email": email, "role": role,
                                          "temporary_password": "temporary password"}).status_code == 201
    other = client.__class__(client.app, headers={"x-nexus-client": "test"})
    other.post("/api/auth/login", json={"email": email, "password": "temporary password"})
    return other


def test_credentials_are_encrypted_and_never_returned(client):
    signup(client)
    conn_id = _connect(client, "Sales", "nexus_demo_sales")
    listed = client.get("/api/connections").json()[0]
    assert listed["secrets_saved"] == ["password"] and "password" not in listed["config"]
    assert demo.READER_PASSWORD not in str(listed)
    ws = client.get("/api/me").json()["workspace"]["id"]
    with tenant(ws) as s:
        stored = row(s, "SELECT secrets_enc FROM connections")["secrets_enc"]
    assert demo.READER_PASSWORD not in stored and stored.startswith("v1:")

    ok = client.post(f"/api/connections/{conn_id}/test").json()
    assert ok["ok"] and "tables visible" in ok["message"]
    bad = _connect(client, "Bad", "nexus_demo_sales", password="wrong-password")
    result = client.post(f"/api/connections/{bad}/test").json()
    assert not result["ok"] and result["message"].startswith("Could not connect")
    assert "wrong-password" not in result["message"]


def test_missing_settings_are_explained(client):
    signup(client)
    r = client.post("/api/connections", json={"kind": "snowflake", "label": "x", "values": {"user": "u"}})
    assert r.status_code == 422 and "Account identifier is required." in r.json()["detail"]


def test_collection_proposes_tables_columns_and_joins(client):
    signup(client)
    _collect_both(client)
    conns = client.get("/api/connections").json()
    assert all(c["collect_status"] == "done" for c in conns)
    assert "Read 4 tables" in conns[0]["collect_msg"]

    tables = _items(client, kind="table")
    assert set(tables) == {"sales.customers", "sales.products", "sales.orders", "sales.order_items",
                           "crm.territories", "crm.reps", "crm.accounts", "crm.activities"}
    assert all(t["status"] == "proposed" and t["origin"] == "discovered" for t in tables.values())
    assert tables["sales.customers"]["attrs"]["comment"] == "Every customer that has bought from us."

    joins = _items(client, kind="join")
    declared = joins["sales.orders.customer_id → sales.customers.id"]
    assert declared["origin"] == "discovered" and declared["attrs"]["evidence"]["declared"]
    # Found from names and data, across the two warehouses: no foreign key declares it.
    cross = joins["crm.accounts.customer_ref → sales.customers.id"]
    assert cross["origin"] == "suggested" and cross["attrs"]["cross_source"]
    assert cross["attrs"]["evidence"]["overlap"] == 1.0 and cross["attrs"]["cardinality"] == "many_to_one"
    assert "crm.activities.account_id → crm.accounts.account_id" in joins
    assert all(j["status"] == "proposed" for j in joins.values())


def test_nothing_reaches_the_graph_until_a_steward_approves(client):
    signup(client)
    _collect_both(client)
    tables, joins = _items(client, kind="table"), _items(client, kind="join")
    customers, activities = tables["sales.customers"]["id"], tables["crm.activities"]["id"]
    assert client.get("/api/graph/paths", params={"from_table": customers, "to_table": activities}).json() == []

    cross = joins["crm.accounts.customer_ref → sales.customers.id"]
    r = client.post("/api/graph/review", json={"item_ids": [cross["id"]], "decision": "approve"})
    assert r.status_code == 409 and "Approve" in r.json()["detail"] and "before" in r.json()["detail"]

    r = client.post("/api/graph/review", json={"item_ids": [t["id"] for t in tables.values()], "decision": "approve"})
    assert r.json()["version"] == 1
    columns = _items(client, kind="column")
    assert all(c["status"] == "approved" for c in columns.values())  # approving a table approves its columns

    wanted = [cross["id"], joins["crm.activities.account_id → crm.accounts.account_id"]["id"]]
    assert client.post("/api/graph/review", json={"item_ids": wanted, "decision": "approve"}).json()["version"] == 2
    paths = client.get("/api/graph/paths", params={"from_table": customers, "to_table": activities}).json()
    assert paths[0]["hops"] == 2 and paths[0]["joins"][0]["cross_source"]

    # Retiring the cross-warehouse join removes the path from the current graph, not from history.
    r = client.post("/api/graph/review", json={"item_ids": [cross["id"]], "decision": "reject", "note": "Wrong key"})
    assert r.json() == {"version": 3, "approved": 0, "deprecated": 1, "rejected": 0}
    assert client.get("/api/graph/paths", params={"from_table": customers, "to_table": activities}).json() == []
    old = client.get("/api/graph/paths", params={"from_table": customers, "to_table": activities, "version": 2})
    assert old.json()[0]["hops"] == 2
    assert [v["number"] for v in client.get("/api/graph/versions").json()] == [3, 2, 1]


def test_a_rejected_suggestion_is_not_proposed_again(client):
    signup(client)
    sales, _ = _collect_both(client)
    cross = _items(client, kind="join")["crm.accounts.customer_ref → sales.customers.id"]
    client.post("/api/graph/review", json={"item_ids": [cross["id"]], "decision": "reject"})
    client.post(f"/api/connections/{sales}/collect")
    jobs.work(HANDLERS, once=True)
    assert _items(client, kind="join")["crm.accounts.customer_ref → sales.customers.id"]["status"] == "rejected"


def test_tables_that_disappear_are_marked(client):
    signup(client)
    owner = demo._url("nexus_demo_sales")
    with psycopg.connect(owner, autocommit=True) as conn:
        conn.execute("CREATE TABLE sales.scratch (id integer)")
        conn.execute("GRANT SELECT ON sales.scratch TO nexus_reader")
    try:
        sales = _connect(client, "Sales", "nexus_demo_sales")
        client.post(f"/api/connections/{sales}/collect")
        jobs.work(HANDLERS, once=True)
        assert _items(client, kind="table")["sales.scratch"]["missing_since"] is None
    finally:
        with psycopg.connect(owner, autocommit=True) as conn:
            conn.execute("DROP TABLE sales.scratch")
    client.post(f"/api/connections/{sales}/collect")
    jobs.work(HANDLERS, once=True)
    assert _items(client, kind="table")["sales.scratch"]["missing_since"] is not None
    assert "1 tables no longer found" in client.get("/api/connections").json()[0]["collect_msg"]


def test_metrics_are_checked_then_approved_by_a_steward(client):
    signup(client)
    _collect_both(client)
    items = _items(client, kind="table")
    developer = _add(client, "developer", "dev@acme.example")
    body = {"name": "Net revenue", "table_id": items["sales.order_items"]["id"], "measure": "sum(net_amount)"}
    bad = developer.post("/api/graph/metrics", json={**body, "measure": "sum(revenue)"})
    assert bad.status_code == 422 and bad.json()["detail"] == "The table has no column named revenue."
    r = developer.post("/api/graph/metrics", json=body)
    assert r.status_code == 201 and r.json()["measure"] == "SUM(net_amount)"
    metric = _items(client, kind="metric")["Net revenue"]
    assert metric["status"] == "proposed" and metric["origin"] == "person"

    assert developer.post("/api/graph/review", json={"item_ids": [metric["id"]], "decision": "approve"}).status_code == 403
    assert client.post("/api/graph/review", json={"item_ids": [metric["id"]], "decision": "approve"}).status_code == 409
    client.post("/api/graph/review", json={"item_ids": [items["sales.order_items"]["id"], metric["id"]],
                                           "decision": "approve"})
    assert _items(client, kind="metric")["Net revenue"]["status"] == "approved"


def test_who_can_see_and_review_the_graph(client):
    signup(client)
    analyst = _add(client, "analyst", "analyst@acme.example")
    steward = _add(client, "steward", "steward@acme.example")
    assert analyst.get("/api/graph/items").status_code == 403
    assert analyst.get("/api/connections").status_code == 403
    assert steward.get("/api/graph/items").status_code == 200
    assert steward.post("/api/connections", json={"kind": "postgres", "label": "x", "values": {}}).status_code == 403


def test_a_connection_with_approved_tables_cannot_be_deleted(client):
    signup(client)
    sales, _ = _collect_both(client)
    table = _items(client, kind="table")["sales.customers"]
    client.post("/api/graph/review", json={"item_ids": [table["id"]], "decision": "approve"})
    assert client.delete(f"/api/connections/{sales}").status_code == 409


def test_workspaces_have_separate_graphs(client):
    signup(client)
    _collect_both(client)
    tables = _items(client, kind="table")
    client.post("/api/graph/review", json={"item_ids": [t["id"] for t in tables.values()], "decision": "approve"})
    ws_a = client.get("/api/me").json()["workspace"]["id"]

    client.cookies.clear()
    signup(client, workspace="Other Co", email="admin@other.example")
    assert client.get("/api/graph/items").json() == []
    ws_b = client.get("/api/me").json()["workspace"]["id"]
    with tenant(ws_b) as s:
        assert s.execute(text("SELECT count(*) FROM kg_cypher('MATCH (t:Table) RETURN {k: t.key}')")).scalar() == 0
    with tenant(ws_a) as s:
        assert s.execute(text("SELECT count(*) FROM kg_cypher('MATCH (t:Table) RETURN {k: t.key}')")).scalar() == 8
    # The app role cannot read any graph directly, only through kg_cypher for its own workspace.
    graph = "kg_" + ws_a.replace("-", "")
    with pytest.raises(DBAPIError, match="permission denied"), tenant(ws_b) as s:
        s.execute(text(f'SELECT * FROM {graph}."Table"'))
