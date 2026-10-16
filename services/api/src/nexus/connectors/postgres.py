"""PostgreSQL. Used by customers whose analytics live in Postgres, and in development
and tests as a stand-in warehouse, so everything runs without cloud accounts."""

from nexus.connectors.base import ColumnMeta, ConnectorError, ForeignKey, TableMeta, Warehouse, normalise_type
from nexus.connectors.spec import Field, Spec, TestResult

SYSTEM_SCHEMAS = ["pg_catalog", "information_schema", "pg_toast", "ag_catalog"]

_COLUMNS = """
SELECT c.table_catalog, c.table_schema, c.table_name, t.table_type, c.column_name, c.data_type,
       c.is_nullable, c.ordinal_position,
       coalesce(col_description(format('%%I.%%I', c.table_schema, c.table_name)::regclass, c.ordinal_position), ''),
       coalesce(obj_description(format('%%I.%%I', c.table_schema, c.table_name)::regclass, 'pg_class'), '')
  FROM information_schema.columns c
  JOIN information_schema.tables t
    ON t.table_schema = c.table_schema AND t.table_name = c.table_name
 WHERE c.table_schema <> ALL(%s) AND c.table_schema NOT LIKE 'pg_temp%%'
   AND t.table_type IN ('BASE TABLE', 'VIEW')
 ORDER BY c.table_schema, c.table_name, c.ordinal_position
"""

# Single-column foreign keys (multi-column keys are not suggested as joins yet).
_FOREIGN_KEYS = """
SELECT current_database(), ns.nspname, cl.relname, att.attname, fns.nspname, fcl.relname, fatt.attname, con.conname
  FROM pg_constraint con
  JOIN pg_class cl ON cl.oid = con.conrelid
  JOIN pg_namespace ns ON ns.oid = cl.relnamespace
  JOIN pg_class fcl ON fcl.oid = con.confrelid
  JOIN pg_namespace fns ON fns.oid = fcl.relnamespace
  JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = con.conkey[1]
  JOIN pg_attribute fatt ON fatt.attrelid = con.confrelid AND fatt.attnum = con.confkey[1]
 WHERE con.contype = 'f' AND cardinality(con.conkey) = 1
"""

SPEC = Spec(
    kind="postgres",
    name="PostgreSQL",
    description="A Postgres database or warehouse.",
    verified=True,
    fields=(
        Field("host", "Host", placeholder="db.internal"),
        Field("port", "Port", default="5432"),
        Field("database", "Database", placeholder="analytics"),
        Field("user", "User", placeholder="nexus_reader", help="A read-only user is enough."),
        Field("password", "Password", secret=True),
        Field("sslmode", "SSL mode", required=False, default="prefer",
              options=("disable", "prefer", "require", "verify-ca", "verify-full")),
    ),
)


class Postgres(Warehouse):
    spec = SPEC
    dialect = "postgres"

    def _connect(self):
        import psycopg

        port = self.settings.get("port") or "5432"
        if not port.isdigit():
            raise ConnectorError("Port must be a number.")
        conn = psycopg.connect(host=self.settings["host"], port=int(port), dbname=self.settings["database"],
                               user=self.settings["user"], password=self.secrets.get("password"),
                               sslmode=self.settings.get("sslmode") or "prefer", connect_timeout=10,
                               autocommit=True)
        # Nexus only reads: refuse writes at the session level as well.
        conn.execute("SET default_transaction_read_only = on")
        conn.execute("SET statement_timeout = '60s'")
        return conn

    def tables(self) -> list[TableMeta]:
        grouped: dict[tuple, dict] = {}
        for db, schema, table, ttype, col, dtype, nullable, ordinal, comment, tcomment in self.query(
                _COLUMNS, (SYSTEM_SCHEMAS,)):
            t = grouped.setdefault((db, schema, table), {"kind": "view" if ttype == "VIEW" else "table",
                                                         "comment": tcomment, "columns": []})
            t["columns"].append(ColumnMeta(col, normalise_type(dtype), dtype, nullable == "YES", ordinal, comment))
        return [TableMeta(db, schema, name, t["kind"], tuple(t["columns"]), t["comment"])
                for (db, schema, name), t in grouped.items()]

    def foreign_keys(self) -> list[ForeignKey]:
        return [ForeignKey(f"{db}.{s}.{t}".lower(), c, f"{db}.{fs}.{ft}".lower(), fc, name)
                for db, s, t, c, fs, ft, fc, name in self.query(_FOREIGN_KEYS)]

    def test(self) -> TestResult:
        version, user = self.query("SELECT split_part(version(), ' on ', 1), current_user")[0]
        (count,) = self.query("SELECT count(*) FROM information_schema.tables WHERE table_schema <> ALL(%s)",
                              (SYSTEM_SCHEMAS,))[0]
        if not count:
            return TestResult(False, f"Connected as {user}, but no tables are visible. Grant USAGE on the schemas "
                                     "and SELECT on the tables Nexus should read.")
        return TestResult(True, f"Connected as {user}. {count} tables visible.",
                          {"version": version, "tables_visible": str(count)})
