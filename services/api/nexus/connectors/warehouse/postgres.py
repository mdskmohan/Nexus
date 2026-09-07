"""PostgreSQL warehouse connector.

Postgres serves two roles in Nexus: an operational source system customers
extract from, and the warehouse the local stack builds into, which makes the
whole pipeline testable without cloud credentials.
"""

from __future__ import annotations

from typing import Any

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
