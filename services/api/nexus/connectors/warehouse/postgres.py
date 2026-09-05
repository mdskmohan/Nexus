"""PostgreSQL warehouse connector.

Reads live schema state from ``information_schema``. Postgres serves two roles in
Nexus: an operational source system customers extract from, and the warehouse the
local stack builds into, which makes the whole pipeline testable without cloud
credentials.

The connection is injected rather than constructed here so the caller owns
credential handling and pooling. This module issues read-only queries and nothing
else — anything that changes a customer system lives behind the policy engine.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from nexus.connectors.base import ConnectorResult
from nexus.connectors.warehouse.schema import (
    Column,
    SchemaSnapshot,
    Table,
    normalise_type,
)
from nexus.graph.entities import Node, NodeKind

SYSTEM = "postgres"

#: Schemas that exist in every database and describe the server, not the data.
_SYSTEM_SCHEMAS = ("pg_catalog", "information_schema", "pg_toast")

#: Ordered by table then ordinal position so a snapshot is deterministic and two
#: captures of an unchanged database compare equal.
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


class Cursor(Protocol):
    """The minimal cursor surface this connector needs."""

    def execute(self, query: str, params: Any = None) -> Any: ...
    def fetchall(self) -> list[Any]: ...


class Connection(Protocol):
    """The minimal connection surface this connector needs."""

    def cursor(self) -> Any: ...


class PostgresConnector:
    """Reads schema state from a live PostgreSQL database."""

    system = SYSTEM

    def __init__(self, connection: Connection, database_label: str | None = None) -> None:
        """
        Args:
            connection: An open DB-API connection. The caller owns its lifecycle.
            database_label: Overrides the catalog name in snapshot keys. Useful when
                a customer's logical warehouse name differs from the physical one.
        """
        self._connection = connection
        self._database_label = database_label

    def snapshot(self) -> SchemaSnapshot:
        """Capture the current schema of every user table and view."""
        # Captured before the query so the timestamp never post-dates the observation.
        captured_at = datetime.now(UTC)

        with self._connection.cursor() as cur:
            cur.execute(_COLUMNS_QUERY, {"system_schemas": list(_SYSTEM_SCHEMAS)})
            rows = cur.fetchall()

        grouped: dict[tuple[str, str, str], list[Column]] = {}
        for catalog, schema, table, column, data_type, is_nullable in rows:
            key = (self._database_label or catalog, schema, table)
            grouped.setdefault(key, []).append(
                Column(
                    name=column,
                    data_type=normalise_type(data_type),
                    nullable=(is_nullable == "YES"),
                    raw_type=data_type,
                )
            )

        tables = tuple(
            Table(database=db, schema=schema, name=name, columns=tuple(cols))
            for (db, schema, name), cols in grouped.items()
        )
        return SchemaSnapshot(captured_at=captured_at, tables=tables, system=SYSTEM)

    def collect(self) -> ConnectorResult:
        """Emit one graph node per table or view currently present."""
        snap = self.snapshot()
        result = ConnectorResult()
        for table in snap.tables:
            result.nodes.append(
                Node(
                    id=f"{SYSTEM}:{table.key}",
                    kind=NodeKind.SOURCE,
                    name=f"{table.schema}.{table.name}",
                    system=SYSTEM,
                    attributes={
                        "database": table.database,
                        "schema": table.schema,
                        "table": table.name,
                        "column_count": str(len(table.columns)),
                    },
                )
            )
        if not result.nodes:
            result.warnings.append(
                "no user tables found; the connection may point at an empty database "
                "or the role may lack visibility into information_schema"
            )
        return result
