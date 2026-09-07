"""Shared behaviour for SQL warehouse connectors.

Postgres, Snowflake and Databricks all expose ``INFORMATION_SCHEMA.COLUMNS`` with
the same essential shape, so snapshot assembly, grouping and node emission live
here once. Subclasses supply three things: the query, the parameters, and how to
read a row.

What genuinely differs per warehouse is the dialect, the system schemas to
exclude, and the type vocabulary — not the logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from nexus.connectors.base import ConnectorResult
from nexus.connectors.warehouse.schema import (
    Column,
    SchemaSnapshot,
    Table,
    normalise_type,
)
from nexus.graph.entities import Node, NodeKind


class SqlWarehouseConnector(ABC):
    """Captures schema state from a SQL warehouse over a DB-API connection.

    The connection is injected rather than constructed here so the caller owns
    credential handling and pooling. Subclasses issue read-only queries and
    nothing else — anything that *changes* a customer system lives behind the
    policy engine.
    """

    #: Stable identifier used in node ids and provenance, e.g. "snowflake".
    system: str

    def __init__(self, connection: Any, database_label: str | None = None) -> None:
        self._connection = connection
        self._database_label = database_label

    @abstractmethod
    def _columns_query(self) -> tuple[str, Any]:
        """Return the query and its parameters for reading column metadata.

        The result must yield rows of
        ``(catalog, schema, table, column, data_type, is_nullable)``
        ordered by schema, table, then ordinal position, so that two captures of
        an unchanged warehouse compare equal.
        """

    def _is_nullable(self, raw: Any) -> bool:
        """Interpret the warehouse's nullability flag.

        All three targets report the SQL-standard 'YES'/'NO' string, but this is
        overridable because drivers occasionally hand back a bool.
        """
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().upper() == "YES"

    def snapshot(self) -> SchemaSnapshot:
        """Capture the current schema of every visible table and view."""
        # Taken before the query so the timestamp never post-dates the observation.
        captured_at = datetime.now(UTC)
        query, params = self._columns_query()

        cursor = self._connection.cursor()
        try:
            cursor.execute(query, params) if params is not None else cursor.execute(query)
            rows = cursor.fetchall()
        finally:
            close = getattr(cursor, "close", None)
            if callable(close):
                close()

        grouped: dict[tuple[str, str, str], list[Column]] = {}
        for catalog, schema, table, column, data_type, is_nullable in rows:
            key = (self._database_label or str(catalog), str(schema), str(table))
            grouped.setdefault(key, []).append(
                Column(
                    name=str(column),
                    data_type=normalise_type(str(data_type)),
                    nullable=self._is_nullable(is_nullable),
                    raw_type=str(data_type),
                )
            )

        tables = tuple(
            Table(database=db, schema=schema, name=name, columns=tuple(cols))
            for (db, schema, name), cols in grouped.items()
        )
        return SchemaSnapshot(captured_at=captured_at, tables=tables, system=self.system)

    def collect(self) -> ConnectorResult:
        """Emit one graph node per table or view currently present."""
        snap = self.snapshot()
        result = ConnectorResult()
        for table in snap.tables:
            result.nodes.append(
                Node(
                    id=f"{self.system}:{table.key}",
                    kind=NodeKind.SOURCE,
                    name=f"{table.schema}.{table.name}",
                    system=self.system,
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
                f"{self.system} reported no user tables; the connection may point at an "
                "empty database, or the role may lack visibility into information_schema"
            )
        return result
