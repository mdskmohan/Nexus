"""Connectors against real databases.

`make warehouses` starts MySQL, SQL Server and Oracle locally; each test loads
the same small sales and CRM data into one of them, then goes through Nexus's
API exactly as a person would: add the connection, test it, read its tables,
and let Nexus suggest joins (which samples real values with that platform's
SQL). A platform that is not running is skipped, not faked.

Snowflake, Databricks, BigQuery, Redshift, SAP HANA and Teradata cannot run
locally; their settings, connection addresses and SQL are checked offline at
the end of this file.
"""

import json
import socket

import pytest

from nexus import jobs
from nexus.connectors import KINDS
from nexus.connectors.base import count_matching_sql
from nexus.runtime.worker import HANDLERS
from tests.conftest import signup


def _up(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


# Loading the demo data into each real database ------------------------------------

def _mysql_setup():
    import pymysql

    conn = pymysql.connect(host="127.0.0.1", port=3307, user="root", password="nexus_root_dev", autocommit=True)
    with conn.cursor() as c:
        for sql in (
            "DROP DATABASE IF EXISTS nx_sales", "DROP DATABASE IF EXISTS nx_crm",
            "CREATE DATABASE nx_sales", "CREATE DATABASE nx_crm",
            "CREATE TABLE nx_sales.customers (id INT PRIMARY KEY, name VARCHAR(100) NOT NULL) COMMENT='Every customer'",
            "CREATE TABLE nx_sales.orders (id INT PRIMARY KEY, customer_id INT NOT NULL, "
            "amount DECIMAL(10,2) COMMENT 'Net amount', FOREIGN KEY (customer_id) REFERENCES nx_sales.customers(id))",
            "CREATE TABLE nx_crm.accounts (account_id VARCHAR(20) PRIMARY KEY, customer_ref INT NOT NULL)",
            "INSERT INTO nx_sales.customers VALUES " + ",".join(f"({i}, 'Customer {i}')" for i in range(1, 51)),
            "INSERT INTO nx_sales.orders VALUES " + ",".join(f"({i}, {1 + i % 50}, {i}.50)" for i in range(1, 201)),
            "INSERT INTO nx_crm.accounts VALUES " + ",".join(f"('ACC-{i}', {i})" for i in range(1, 41)),
        ):
            c.execute(sql)
    conn.close()


def _sqlserver_setup():
    import pymssql

    conn = pymssql.connect(server="127.0.0.1", port=1434, user="sa", password="Nexus_dev_2026!", autocommit=True)
    c = conn.cursor()
    c.execute("IF DB_ID('nx_demo') IS NOT NULL BEGIN ALTER DATABASE nx_demo SET SINGLE_USER WITH ROLLBACK IMMEDIATE; "
              "DROP DATABASE nx_demo; END")
    c.execute("CREATE DATABASE nx_demo")
    conn.close()
    conn = pymssql.connect(server="127.0.0.1", port=1434, user="sa", password="Nexus_dev_2026!", database="nx_demo",
                           autocommit=True)
    c = conn.cursor()
    for sql in (
        "CREATE SCHEMA sales", "CREATE SCHEMA crm",
        "CREATE TABLE sales.customers (id INT PRIMARY KEY, name NVARCHAR(100) NOT NULL)",
        "CREATE TABLE sales.orders (id INT PRIMARY KEY, customer_id INT NOT NULL REFERENCES sales.customers(id), "
        "amount DECIMAL(10,2))",
        "CREATE TABLE crm.accounts (account_id NVARCHAR(20) PRIMARY KEY, customer_ref INT NOT NULL)",
        "INSERT INTO sales.customers VALUES " + ",".join(f"({i}, 'Customer {i}')" for i in range(1, 51)),
        "INSERT INTO sales.orders VALUES " + ",".join(f"({i}, {1 + i % 50}, {i}.50)" for i in range(1, 201)),
        "INSERT INTO crm.accounts VALUES " + ",".join(f"('ACC-{i}', {i})" for i in range(1, 41)),
        "EXEC sp_addextendedproperty 'MS_Description', 'Every customer', 'SCHEMA', 'sales', 'TABLE', 'customers'",
    ):
        c.execute(sql)
    conn.close()


def _oracle_setup():
    import oracledb

    conn = oracledb.connect(user="system", password="nexus_oracle_dev", dsn="127.0.0.1:1522/FREEPDB1")
    c = conn.cursor()
    for user in ("NX_SALES", "NX_CRM"):
        c.execute(f"SELECT count(*) FROM all_users WHERE username = '{user}'")
        if c.fetchone()[0]:
            c.execute(f"DROP USER {user} CASCADE")
        c.execute(f"CREATE USER {user} IDENTIFIED BY nx_pass_123 QUOTA UNLIMITED ON USERS")
    for sql in (
        "CREATE TABLE NX_SALES.CUSTOMERS (ID NUMBER(10) PRIMARY KEY, NAME VARCHAR2(100) NOT NULL)",
        "COMMENT ON TABLE NX_SALES.CUSTOMERS IS 'Every customer'",
        "CREATE TABLE NX_SALES.ORDERS (ID NUMBER(10) PRIMARY KEY, CUSTOMER_ID NUMBER(10) NOT NULL "
        "REFERENCES NX_SALES.CUSTOMERS(ID), AMOUNT NUMBER(10,2))",
        "CREATE TABLE NX_CRM.ACCOUNTS (ACCOUNT_ID VARCHAR2(20) PRIMARY KEY, CUSTOMER_REF NUMBER(10) NOT NULL)",
    ):
        c.execute(sql)
    c.executemany("INSERT INTO NX_SALES.CUSTOMERS VALUES (:1, :2)", [(i, f"Customer {i}") for i in range(1, 51)])
    c.executemany("INSERT INTO NX_SALES.ORDERS VALUES (:1, :2, :3)", [(i, 1 + i % 50, i + 0.5) for i in range(1, 201)])
    c.executemany("INSERT INTO NX_CRM.ACCOUNTS VALUES (:1, :2)", [(f"ACC-{i}", i) for i in range(1, 41)])
    conn.commit()
    conn.close()


PLATFORMS = {
    "mysql": dict(port=3307, setup=_mysql_setup, sales="nx_sales", crm="nx_crm", values={
        "host": "127.0.0.1", "port": "3307", "user": "root", "password": "nexus_root_dev",
        "schemas_include": "^nx_"}),
    "sqlserver": dict(port=1434, setup=_sqlserver_setup, sales="sales", crm="crm", values={
        "host": "127.0.0.1", "port": "1434", "database": "nx_demo", "user": "sa", "password": "Nexus_dev_2026!"}),
    "oracle": dict(port=1522, setup=_oracle_setup, sales="nx_sales", crm="nx_crm", values={
        "host": "127.0.0.1", "port": "1522", "service": "FREEPDB1", "user": "system",
        "password": "nexus_oracle_dev", "schemas_include": "^nx_"}),
}


@pytest.fixture(params=list(PLATFORMS), ids=list(PLATFORMS))
def platform(request):
    kind = request.param
    p = PLATFORMS[kind]
    if not _up(p["port"]):
        pytest.skip(f"{kind} is not running (make warehouses)")
    p["setup"]()
    return kind, p


def test_a_real_warehouse_end_to_end(client, platform):
    kind, p = platform
    signup(client)
    r = client.post("/api/connections", json={"kind": kind, "label": kind, "values": p["values"]})
    assert r.status_code == 201, r.text
    conn_id = r.json()["id"]

    test = client.post(f"/api/connections/{conn_id}/test").json()
    assert test["ok"], test
    assert set(test["details"]) >= {"Check access", "List schemas", "List tables", "List views"}
    assert all(v == "passed" for v in test["details"].values()), test["details"]

    client.post(f"/api/connections/{conn_id}/collect")
    jobs.work(HANDLERS, once=True)
    status = client.get("/api/connections").json()[0]
    assert status["collect_status"] == "done", status["collect_msg"]

    items = {i["name"]: i for i in client.get("/api/graph/items").json()}
    sales, crm = p["sales"], p["crm"]
    assert {f"{sales}.customers", f"{sales}.orders", f"{crm}.accounts"} <= set(items)
    assert all(not name.startswith(("sys.", "information_schema", "mysql.")) for name in items)
    orders = items[f"{sales}.orders"]
    assert orders["attrs"]["column_count"] == 3
    assert items[f"{sales}.customers"]["attrs"]["comment"] == "Every customer"

    # The declared key, and a join found only from names and sampled data, both read for real.
    declared = items[f"{sales}.orders.customer_id → {sales}.customers.id"]
    assert declared["attrs"]["evidence"]["declared"]
    found = items[f"{crm}.accounts.customer_ref → {sales}.customers.id"]
    assert found["origin"] == "suggested"
    assert found["attrs"]["evidence"]["overlap"] == 1.0 and found["attrs"]["evidence"]["right_key_ratio"] == 1.0


def test_a_wrong_password_is_reported_plainly(client, platform):
    kind, p = platform
    signup(client)
    values = {**p["values"], "password": "wrong-password-123"}
    conn_id = client.post("/api/connections", json={"kind": kind, "label": kind, "values": values}).json()["id"]
    result = client.post(f"/api/connections/{conn_id}/test").json()
    assert not result["ok"] and result["message"].startswith("Could not connect")
    assert "wrong-password-123" not in result["message"]


# Platforms that cannot run locally: checked offline -----------------------------------

KEY = json.dumps({"type": "service_account", "project_id": "acme"})
OFFLINE = {
    "snowflake": ({"account": "xy123", "user": "u", "warehouse": "W", "database": "D"}, {"password": "p"}, None),
    "databricks": ({"server_hostname": "h", "http_path": "/sql/1.0/x"}, {"access_token": "t"}, None),
    "bigquery": ({"project_id": "acme"}, {"credentials": KEY}, "bigquery://acme"),
    "redshift": ({"host": "h", "database": "dev", "user": "u"}, {"password": "p"},
                 "redshift+redshift_connector://u:***@h:5439/dev"),
    "saphana": ({"host": "h", "user": "u"}, {"password": "p"},
                "hana://u:***@h:443?encrypt=true&sslValidateCertificate=true"),
    "teradata": ({"host": "h", "user": "u"}, {"password": "p"},
                 "teradatasql://u:***@h?connect_timeout=20000&dbs_port=1025&logmech=TD2&tmode=DEFAULT"),
}


@pytest.mark.parametrize("kind", list(OFFLINE))
def test_platforms_that_cannot_run_locally(kind):
    settings, secrets, url = OFFLINE[kind]
    cls = KINDS[kind]
    assert cls.spec.problems(settings, secrets) == []
    wh = cls(settings, secrets)
    if url:
        assert wh.url().render_as_string(hide_password=True) == url
    sql = count_matching_sql(wh, "db", "sales", "orders", "customer_id", [1, 2], True)
    assert "COUNT(DISTINCT" in sql and "IN (1, 2)" in sql


def test_all_ten_platforms_are_offered(client):
    signup(client)
    kinds = [k["kind"] for k in client.get("/api/connections/kinds").json()]
    assert kinds == ["snowflake", "databricks", "sqlserver", "oracle", "bigquery", "redshift", "saphana",
                     "postgres", "teradata", "mysql"]


def test_entra_sign_in_needs_the_odbc_driver():
    from nexus.connectors.base import ConnectorError

    wh = KINDS["sqlserver"]({"host": "h", "database": "d", "user": "u", "authentication": "entra_password"},
                            {"password": "p"})
    with pytest.raises(ConnectorError, match="ODBC driver"):
        wh.url()


def test_schema_filters():
    from nexus.connectors.base import schema_allowed

    assert schema_allowed({"schemas_include": "^sales$, ^fin"}, "finance")
    assert not schema_allowed({"schemas_include": "^sales$"}, "crm")
    assert not schema_allowed({"schemas_exclude": "_tmp$"}, "sales_tmp")
    assert schema_allowed({}, "anything")
