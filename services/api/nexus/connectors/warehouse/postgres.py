"""PostgreSQL warehouse connector.

Postgres serves two roles in Nexus: an operational source system customers
extract from, and the warehouse the local stack builds into, which makes the
whole pipeline testable without cloud credentials.
"""

from __future__ import annotations

from typing import Any

from nexus.connectors.spec import (
    Category,
    ConnectionField,
    ConnectionTestResult,
    ConnectorSpec,
    FieldType,
)
from nexus.connectors.warehouse.base import SqlWarehouseConnector

SYSTEM = "postgres"

#: Present in every database; they describe the server, not the customer's data.
SYSTEM_SCHEMAS = ("pg_catalog", "information_schema", "pg_toast")

_COLUMNS_QUERY = """
SELECT c.table_catalog,
       c.table_schema,
       c.table_name,
       c.column_name,
       c.data_type,
       c.is_nullable
  FROM information_schema.columns AS c
  JOIN information_schema.tables AS t
    ON t.table_catalog = c.table_catalog
   AND t.table_schema  = c.table_schema
   AND t.table_name    = c.table_name
 WHERE c.table_schema <> ALL(%(system_schemas)s)
   AND t.table_type IN ('BASE TABLE', 'VIEW')
 ORDER BY c.table_schema, c.table_name, c.ordinal_position
"""


class PostgresConnector(SqlWarehouseConnector):
    """Reads schema state from a live PostgreSQL database."""

    system = SYSTEM

    def _columns_query(self) -> tuple[str, Any]:
        return _COLUMNS_QUERY, {"system_schemas": list(SYSTEM_SCHEMAS)}


SPEC = ConnectorSpec(
    id=SYSTEM,
    name="PostgreSQL",
    category=Category.DATABASE,
    description="Read schema history from an operational database or a Postgres warehouse.",
    driver_package="psycopg[binary]",
    verified=True,
    fields=(
        ConnectionField(name="host", label="Host", placeholder="db.internal"),
        ConnectionField(
            name="port", label="Port", type=FieldType.NUMBER, default="5432"
        ),
        ConnectionField(name="database", label="Database", placeholder="analytics"),
        ConnectionField(name="user", label="User", placeholder="nexus_readonly"),
        ConnectionField(name="password", label="Password", type=FieldType.SECRET),
        ConnectionField(
            name="sslmode",
            label="SSL mode",
            type=FieldType.SELECT,
            required=False,
            default="prefer",
            options=("disable", "prefer", "require", "verify-ca", "verify-full"),
        ),
    ),
)


def connect(config: dict[str, Any]) -> Any:
    """Open a Postgres connection from a validated configuration."""
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise RuntimeError("the Postgres driver is not installed") from exc

    return psycopg.connect(
        host=config["host"],
        port=int(config.get("port") or 5432),
        dbname=config["database"],
        user=config["user"],
        password=config.get("password"),
        sslmode=config.get("sslmode") or "prefer",
        connect_timeout=10,
        autocommit=True,
    )


def test_connection(config: dict[str, Any]) -> ConnectionTestResult:
    """Probe a Postgres configuration by counting the tables the role can see."""
    try:
        connection = connect(config)
    except Exception as exc:  # noqa: BLE001
        return ConnectionTestResult.failure(str(exc).strip().splitlines()[0][:300])

    try:
        with connection.cursor() as cur:
            cur.execute("SELECT version(), current_user")
            version, user = cur.fetchone()
            cur.execute(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema <> ALL(%s)",
                (list(SYSTEM_SCHEMAS),),
            )
            (table_count,) = cur.fetchone()
    except Exception as exc:  # noqa: BLE001
        return ConnectionTestResult.failure(str(exc).strip().splitlines()[0][:300])
    finally:
        connection.close()

    if not table_count:
        return ConnectionTestResult.failure(
            f"Connected as {user}, but no tables are visible. Grant USAGE on the "
            "schemas and SELECT on the tables Nexus should observe."
        )
    return ConnectionTestResult.success(
        f"Connected as {user}",
        version=str(version).split(" on ")[0],
        tables_visible=str(table_count),
    )
