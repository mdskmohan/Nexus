"""Databricks lakehouse connector.

Unity Catalog exposes ``system.information_schema.columns``, which spans every
catalog in the metastore, so one connection observes the whole workspace. On
workspaces without Unity Catalog the connector falls back to a single catalog's
own information_schema.

Requires the ``databricks-sql-connector`` extra.
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

SYSTEM = "databricks"

#: Unity Catalog's own metadata catalogs, which describe the platform not the data.
SYSTEM_CATALOGS = ("system", "__databricks_internal")

_UNITY_QUERY = """
SELECT table_catalog,
       table_schema,
       table_name,
       column_name,
       full_data_type,
       is_nullable
  FROM system.information_schema.columns
 WHERE table_catalog NOT IN ('system', '__databricks_internal')
   AND table_schema <> 'information_schema'
 ORDER BY table_catalog, table_schema, table_name, ordinal_position
"""

_SINGLE_CATALOG_QUERY = """
SELECT table_catalog,
       table_schema,
       table_name,
       column_name,
       full_data_type,
       is_nullable
  FROM {catalog}.information_schema.columns
 WHERE table_schema <> 'information_schema'
 ORDER BY table_schema, table_name, ordinal_position
"""

SPEC = ConnectorSpec(
    id=SYSTEM,
    name="Databricks",
    category=Category.LAKEHOUSE,
    description="Read Unity Catalog schema and lineage; compile pipelines onto Databricks.",
    driver_package="databricks-sql-connector",
    docs_url="https://docs.databricks.com/en/integrations/compute-details.html",
    verified=False,
    fields=(
        ConnectionField(
            name="server_hostname",
            label="Workspace hostname",
            placeholder="dbc-a1b2c3d4-e5f6.cloud.databricks.com",
            help="Without the https:// prefix.",
        ),
        ConnectionField(
            name="http_path",
            label="SQL warehouse HTTP path",
            placeholder="/sql/1.0/warehouses/abc123def456",
            help="From the SQL warehouse's Connection details tab.",
        ),
        ConnectionField(
            name="access_token",
            label="Personal access token",
            type=FieldType.SECRET,
            help="Generate under Settings → Developer → Access tokens.",
        ),
        ConnectionField(
            name="catalog",
            label="Catalog",
            required=False,
            placeholder="main",
            help="Leave blank to observe every catalog via Unity Catalog. "
            "Set it to scope to one catalog, or if Unity Catalog is not enabled.",
        ),
    ),
)


def connect(config: dict[str, Any]) -> Any:
    """Open a Databricks SQL connection from a validated configuration."""
    try:
        from databricks import sql
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise RuntimeError(
            "the Databricks driver is not installed; add the 'databricks' extra"
        ) from exc

    # The driver retries a dead host indefinitely by default, which hangs the
    # caller rather than failing. A typo in the hostname must surface as an error
    # in seconds, not never.
    return sql.connect(
        server_hostname=config["server_hostname"].replace("https://", "").rstrip("/"),
        http_path=config["http_path"],
        access_token=config["access_token"],
        _socket_timeout=15,
        _retry_stop_after_attempts_count=2,
        _retry_delay_max=5,
    )


class DatabricksConnector(SqlWarehouseConnector):
    """Reads schema state from a live Databricks workspace."""

    system = SYSTEM

    def __init__(
        self,
        connection: Any,
        catalog: str | None = None,
        database_label: str | None = None,
    ) -> None:
        super().__init__(connection, database_label)
        self._catalog = catalog

    def _columns_query(self) -> tuple[str, Any]:
        if self._catalog:
            return _SINGLE_CATALOG_QUERY.format(catalog=self._catalog), None
        return _UNITY_QUERY, None


def test_connection(config: dict[str, Any]) -> ConnectionTestResult:
    """Probe a Databricks configuration by reading its catalog.

    Unity Catalog is tried first; a workspace without it falls back to the named
    catalog, and the error explains that distinction rather than reporting a bare
    permission failure.
    """
    try:
        connection = connect(config)
    except Exception as exc:  # noqa: BLE001
        return ConnectionTestResult.failure(_clean(exc))

    catalog = config.get("catalog") or ""
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT current_version().dbsql_version, current_user()")
        row = cursor.fetchone()
        version, user = (row[0], row[1]) if row else ("unknown", "unknown")

        if catalog:
            cursor.execute(
                f"SELECT COUNT(*) FROM {catalog}.information_schema.tables "
                "WHERE table_schema <> 'information_schema'"
            )
            scope = f"catalog {catalog}"
        else:
            try:
                cursor.execute(
                    "SELECT COUNT(*) FROM system.information_schema.tables "
                    "WHERE table_catalog NOT IN ('system', '__databricks_internal')"
                )
                scope = "Unity Catalog"
            except Exception:  # noqa: BLE001
                cursor.close()
                connection.close()
                return ConnectionTestResult.failure(
                    "Connected, but system.information_schema is unreadable. This "
                    "workspace may not have Unity Catalog enabled — set a Catalog to "
                    "scope the connection to one instead."
                )
        (table_count,) = cursor.fetchone()
        cursor.close()
    except Exception as exc:  # noqa: BLE001
        return ConnectionTestResult.failure(_clean(exc))
    finally:
        connection.close()

    if not table_count:
        return ConnectionTestResult.failure(
            f"Connected as {user}, but no tables are visible via {scope}. "
            "Grant this principal USE CATALOG and SELECT."
        )
    return ConnectionTestResult.success(
        f"Connected to Databricks SQL {version} as {user}",
        version=str(version),
        user=str(user),
        scope=scope,
        tables_visible=str(table_count),
    )


def _clean(exc: Exception) -> str:
    """Render a driver error without leaking the configuration back to the user."""
    text = str(exc).strip().splitlines()[0] if str(exc).strip() else exc.__class__.__name__
    return text[:300]
