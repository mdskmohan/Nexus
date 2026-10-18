"""Databricks SQL. With Unity Catalog one connection sees every catalog the
principal can read; set a catalog to narrow it (or when Unity Catalog is off).

Not yet exercised against a real Databricks workspace.
"""

from nexus.connectors.base import ColumnMeta, ForeignKey, TableMeta, Warehouse, normalise_type
from nexus.connectors.spec import FILTERS, Field, Spec, TestResult

_SYSTEM_CATALOGS = "('system', '__databricks_internal', 'samples')"

_COLUMNS = """
SELECT c.table_catalog, c.table_schema, c.table_name, t.table_type, c.column_name, c.full_data_type,
       c.is_nullable, c.ordinal_position, coalesce(c.comment, ''), coalesce(t.comment, '')
  FROM {scope}.columns c
  JOIN {scope}.tables t
    ON t.table_catalog = c.table_catalog AND t.table_schema = c.table_schema AND t.table_name = c.table_name
 WHERE c.table_catalog NOT IN {system} AND c.table_schema <> 'information_schema'
 ORDER BY c.table_catalog, c.table_schema, c.table_name, c.ordinal_position
"""

# Informational foreign keys declared in Unity Catalog (single-column only).
_FOREIGN_KEYS = """
SELECT k.table_catalog, k.table_schema, k.table_name, k.column_name,
       u.table_catalog, u.table_schema, u.table_name, u.column_name, k.constraint_name
  FROM {scope}.referential_constraints r
  JOIN {scope}.key_column_usage k
    ON k.constraint_catalog = r.constraint_catalog AND k.constraint_schema = r.constraint_schema
   AND k.constraint_name = r.constraint_name
  JOIN {scope}.key_column_usage u
    ON u.constraint_catalog = r.unique_constraint_catalog AND u.constraint_schema = r.unique_constraint_schema
   AND u.constraint_name = r.unique_constraint_name AND u.ordinal_position = k.position_in_unique_constraint
 WHERE k.table_catalog NOT IN {system}
"""

SPEC = Spec(
    kind="databricks",
    name="Databricks",
    description="Databricks SQL warehouses on Unity Catalog. Reads catalogs, schemas, tables and views with a personal access token or service principal token.",
    docs_url="https://docs.databricks.com/en/integrations/compute-details.html",
    fields=(
        Field("server_hostname", "Workspace hostname", placeholder="dbc-a1b2c3d4-e5f6.cloud.databricks.com",
              help="Without https://."),
        Field("http_path", "SQL warehouse HTTP path", placeholder="/sql/1.0/warehouses/abc123def456",
              help="From the SQL warehouse's Connection details tab."),
        Field("access_token", "Access token", secret=True,
              help="A token for a service principal with read access."),
        Field("catalog", "Catalog", required=False, placeholder="main",
              help="Leave blank to read every catalog through Unity Catalog."),
        *FILTERS,
    ),
)


class Databricks(Warehouse):
    spec = SPEC
    dialect = "databricks"

    def _connect(self):
        from databricks import sql

        # The driver retries a dead host for a long time by default; fail in seconds instead.
        return sql.connect(server_hostname=self.settings["server_hostname"].replace("https://", "").rstrip("/"),
                           http_path=self.settings["http_path"], access_token=self.secrets["access_token"],
                           _socket_timeout=30, _retry_stop_after_attempts_count=2, _retry_delay_max=5)

    def _scope(self) -> str:
        catalog = self.settings.get("catalog")
        return f"`{catalog.replace('`', '')}`.information_schema" if catalog else "system.information_schema"

    def tables(self) -> list[TableMeta]:
        grouped: dict[tuple, dict] = {}
        rows = self.query(_COLUMNS.format(scope=self._scope(), system=_SYSTEM_CATALOGS))
        for db, schema, table, ttype, col, dtype, nullable, ordinal, comment, tcomment in rows:
            t = grouped.setdefault((db, schema, table), {"kind": "view" if "VIEW" in (ttype or "") else "table",
                                                         "comment": tcomment, "columns": []})
            t["columns"].append(ColumnMeta(col, normalise_type(dtype), dtype, nullable == "YES", ordinal, comment))
        return [TableMeta(db, schema, name, t["kind"], tuple(t["columns"]), t["comment"])
                for (db, schema, name), t in grouped.items()]

    def foreign_keys(self) -> list[ForeignKey]:
        rows = self.query(_FOREIGN_KEYS.format(scope=self._scope(), system=_SYSTEM_CATALOGS))
        return [ForeignKey(f"{c}.{s}.{t}".lower(), col, f"{rc}.{rs}.{rt}".lower(), rcol, name)
                for c, s, t, col, rc, rs, rt, rcol, name in rows]

    def test(self) -> TestResult:
        user = self.query("SELECT current_user()")[0][0]
        (count,) = self.query(f"SELECT COUNT(*) FROM {self._scope()}.tables "
                              f"WHERE table_catalog NOT IN {_SYSTEM_CATALOGS} AND table_schema <> 'information_schema'")[0]
        if not count:
            return TestResult(False, f"Connected as {user}, but no tables are visible. "
                                     "Grant this principal USE CATALOG, USE SCHEMA and SELECT.")
        return TestResult(True, f"Connected to Databricks as {user}. {count} tables visible.",
                          {"user": str(user), "tables_visible": str(count)})
