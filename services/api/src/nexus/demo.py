"""Two demo warehouses on the local Postgres, so everything can be tried without cloud accounts.

`nexus_demo_sales` stands in for a Snowflake sales mart; `nexus_demo_crm` for a
Databricks CRM lakehouse. They are separate databases, joined by
`crm.accounts.customer_ref` → `sales.customers.id`, which no foreign key
declares: Nexus has to find it from names and data.

    nexus-seed-demo --email you@example.com

creates (or recreates) both databases and adds them as connections to that
person's workspace.
"""

import argparse
import json
import sys

import psycopg

from nexus.config import settings

READER, READER_PASSWORD = "nexus_reader", "nexus_reader_dev"

SALES = """
CREATE SCHEMA sales;
CREATE TABLE sales.customers (
    id integer PRIMARY KEY, name text NOT NULL, region text NOT NULL, segment text NOT NULL);
COMMENT ON TABLE sales.customers IS 'Every customer that has bought from us.';
CREATE TABLE sales.products (
    id integer PRIMARY KEY, name text NOT NULL, category text NOT NULL, list_price numeric(10, 2) NOT NULL);
CREATE TABLE sales.orders (
    id integer PRIMARY KEY, customer_id integer NOT NULL REFERENCES sales.customers(id),
    order_date date NOT NULL, status text NOT NULL);
COMMENT ON COLUMN sales.orders.status IS 'complete, cancelled or returned';
CREATE TABLE sales.order_items (
    order_id integer NOT NULL REFERENCES sales.orders(id), product_id integer NOT NULL REFERENCES sales.products(id),
    quantity integer NOT NULL, net_amount numeric(12, 2) NOT NULL);

INSERT INTO sales.customers
SELECT i, 'Customer ' || i, (ARRAY['North', 'South', 'East', 'West'])[1 + i % 4],
       (ARRAY['Enterprise', 'Mid-market', 'SMB'])[1 + i % 3]
  FROM generate_series(1, 200) i;
INSERT INTO sales.products
SELECT i, 'Product ' || i, (ARRAY['Hardware', 'Software', 'Services'])[1 + i % 3], 50 + i * 7
  FROM generate_series(1, 30) i;
INSERT INTO sales.orders
SELECT i, 1 + (i * 37) % 200, date '2026-01-01' + (i % 270),
       (ARRAY['complete', 'complete', 'complete', 'cancelled', 'returned'])[1 + i % 5]
  FROM generate_series(1, 1500) i;
INSERT INTO sales.order_items
SELECT o, 1 + (o * 13 + n) % 30, 1 + (o + n) % 4, round(((1 + (o + n) % 4) * (50 + ((o * 13 + n) % 30) * 7))::numeric, 2)
  FROM generate_series(1, 1500) o, generate_series(1, 2) n;
"""

CRM = """
CREATE SCHEMA crm;
CREATE TABLE crm.territories (id integer PRIMARY KEY, name text NOT NULL, region text NOT NULL);
CREATE TABLE crm.reps (rep_id integer PRIMARY KEY, name text NOT NULL,
                       territory_id integer NOT NULL REFERENCES crm.territories(id));
CREATE TABLE crm.accounts (
    account_id text PRIMARY KEY, customer_ref integer NOT NULL, owner_rep_id integer NOT NULL,
    industry text NOT NULL, created_on date NOT NULL);
COMMENT ON COLUMN crm.accounts.customer_ref IS 'The customer number in the sales system';
CREATE TABLE crm.activities (
    activity_id integer PRIMARY KEY, account_id text NOT NULL, rep_id integer NOT NULL,
    kind text NOT NULL, happened_on date NOT NULL);

INSERT INTO crm.territories
SELECT i, 'Territory ' || i, (ARRAY['North', 'South', 'East', 'West'])[1 + i % 4] FROM generate_series(1, 8) i;
INSERT INTO crm.reps SELECT i, 'Rep ' || i, 1 + i % 8 FROM generate_series(1, 24) i;
INSERT INTO crm.accounts
SELECT 'ACC-' || lpad(i::text, 4, '0'), i, 1 + i % 24,
       (ARRAY['Manufacturing', 'Retail', 'Healthcare', 'Finance'])[1 + i % 4], date '2025-01-01' + i
  FROM generate_series(1, 180) i;
INSERT INTO crm.activities
SELECT i, 'ACC-' || lpad((1 + i % 180)::text, 4, '0'), 1 + i % 24,
       (ARRAY['call', 'email', 'meeting'])[1 + i % 3], date '2026-01-01' + (i % 270)
  FROM generate_series(1, 2000) i;
"""

DATABASES = {"nexus_demo_sales": ("sales", SALES), "nexus_demo_crm": ("crm", CRM)}


def _url(database: str) -> str:
    return settings().database_owner_url.replace("postgresql+psycopg://", "postgresql://").rsplit("/", 1)[0] + "/" + database


def install() -> None:
    """(Re)create both demo databases and a read-only role that can read them."""
    with psycopg.connect(_url("postgres"), autocommit=True) as admin:
        if not admin.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (READER,)).fetchone():
            admin.execute(f"CREATE ROLE {READER} LOGIN PASSWORD '{READER_PASSWORD}'")
        for database in DATABASES:
            admin.execute(f"DROP DATABASE IF EXISTS {database} WITH (FORCE)")
            admin.execute(f"CREATE DATABASE {database}")
    for database, (schema, sql) in DATABASES.items():
        with psycopg.connect(_url(database), autocommit=True) as conn:
            conn.execute(sql)
            conn.execute(f"GRANT CONNECT ON DATABASE {database} TO {READER}")
            conn.execute(f"GRANT USAGE ON SCHEMA {schema} TO {READER}")
            conn.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA {schema} TO {READER}")


def connection_values(database: str) -> dict:
    host_port = settings().database_owner_url.rsplit("@", 1)[1].rsplit("/", 1)[0]
    host, _, port = host_port.partition(":")
    return {"host": host, "port": port or "5432", "database": database, "user": READER,
            "password": READER_PASSWORD, "sslmode": "disable"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the demo warehouses and connect them to a workspace.")
    parser.add_argument("--email", required=True, help="a member of the workspace to add the connections to")
    args = parser.parse_args()

    from nexus import audit, connections
    from nexus.connectors.postgres import SPEC
    from nexus.db import row, scalar, tenant, unscoped
    from nexus.graph.collect import start_run

    with unscoped() as s:
        user = row(s, "SELECT * FROM auth_lookup(:e)", e=args.email)
    if user is None:
        sys.exit(f"No account for {args.email}. Sign up at http://localhost:3100 first.")
    install()
    workspace_id = str(user["workspace_id"])
    with tenant(workspace_id) as s:
        for label, database in (("Sales warehouse (demo)", "nexus_demo_sales"),
                                ("CRM lakehouse (demo)", "nexus_demo_crm")):
            settings_, secrets_ = SPEC.split(connection_values(database))
            existing = row(s, "SELECT id FROM connections WHERE label = :l", l=label)
            if existing:
                connection_id = existing["id"]
            else:
                connection_id = scalar(s, """INSERT INTO connections (workspace_id, kind, label, config, secrets_enc, created_by)
                                             VALUES (:w, 'postgres', :l, CAST(:c AS jsonb), :s, :u) RETURNING id""",
                                       w=workspace_id, l=label, c=json.dumps(settings_),
                                       s=connections.seal(secrets_, workspace_id), u=user["id"])
                audit.record(s, workspace_id, user["id"], "connection.added", "connection", connection_id, kind="postgres")
            start_run(s, workspace_id, str(connection_id), trigger="setup", user_id=str(user["id"]))
    print("Demo warehouses created and connected. The worker is reading them now;\n"
          "open http://localhost:3100/knowledge to review what it found.")
