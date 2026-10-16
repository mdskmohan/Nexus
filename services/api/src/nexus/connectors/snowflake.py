"""Snowflake. One connection per database; the role decides what Nexus can see.

Not yet exercised against a real Snowflake account.
"""

from nexus.connectors.base import ColumnMeta, ForeignKey, TableMeta, Warehouse, normalise_type
from nexus.connectors.spec import Field, Spec, TestResult

_COLUMNS = """
SELECT c.TABLE_CATALOG, c.TABLE_SCHEMA, c.TABLE_NAME, t.TABLE_TYPE, c.COLUMN_NAME, c.DATA_TYPE, c.IS_NULLABLE,
       c.ORDINAL_POSITION, COALESCE(c.COMMENT, ''), COALESCE(t.COMMENT, '')
  FROM INFORMATION_SCHEMA.COLUMNS c
  JOIN INFORMATION_SCHEMA.TABLES t
    ON t.TABLE_CATALOG = c.TABLE_CATALOG AND t.TABLE_SCHEMA = c.TABLE_SCHEMA AND t.TABLE_NAME = c.TABLE_NAME
 WHERE c.TABLE_SCHEMA <> 'INFORMATION_SCHEMA' AND t.TABLE_TYPE IN ('BASE TABLE', 'VIEW')
 ORDER BY c.TABLE_SCHEMA, c.TABLE_NAME, c.ORDINAL_POSITION
"""

SPEC = Spec(
    kind="snowflake",
    name="Snowflake",
    description="One Snowflake database. Use a read-only role.",
    docs_url="https://docs.snowflake.com/en/user-guide/admin-account-identifier",
    fields=(
        Field("account", "Account identifier", placeholder="xy12345.eu-west-1",
              help="From your Snowflake URL: the part before .snowflakecomputing.com."),
        Field("user", "User", placeholder="NEXUS_SVC"),
        Field("password", "Password", required=False, secret=True, help="Leave blank to use a private key."),
        Field("private_key", "Private key (PEM)", required=False, secret=True, multiline=True,
              help="Key-pair authentication; preferred for service users."),
        Field("private_key_passphrase", "Private key passphrase", required=False, secret=True),
        Field("warehouse", "Warehouse", placeholder="COMPUTE_WH"),
        Field("database", "Database", placeholder="ANALYTICS"),
        Field("role", "Role", required=False, placeholder="NEXUS_READONLY"),
    ),
)


class Snowflake(Warehouse):
    spec = SPEC
    dialect = "snowflake"

    def _connect(self):
        import snowflake.connector

        params = {"account": self.settings["account"], "user": self.settings["user"],
                  "warehouse": self.settings.get("warehouse"), "database": self.settings.get("database"),
                  "autocommit": True, "client_session_keep_alive": False, "login_timeout": 20,
                  "network_timeout": 60}
        if self.settings.get("role"):
            params["role"] = self.settings["role"]
        if self.secrets.get("private_key"):
            params["private_key"] = _der(self.secrets["private_key"], self.secrets.get("private_key_passphrase"))
        else:
            params["password"] = self.secrets.get("password")
        return snowflake.connector.connect(**params)

    def tables(self) -> list[TableMeta]:
        grouped: dict[tuple, dict] = {}
        for db, schema, table, ttype, col, dtype, nullable, ordinal, comment, tcomment in self.query(_COLUMNS):
            t = grouped.setdefault((db, schema, table), {"kind": "view" if ttype == "VIEW" else "table",
                                                         "comment": tcomment, "columns": []})
            t["columns"].append(ColumnMeta(col, normalise_type(dtype), dtype, nullable == "YES", ordinal, comment))
        return [TableMeta(db, schema, name, t["kind"], tuple(t["columns"]), t["comment"])
                for (db, schema, name), t in grouped.items()]

    def foreign_keys(self) -> list[ForeignKey]:
        # Snowflake records declared (unenforced) keys; SHOW returns them by column name.
        cursor = self._conn.cursor()
        try:
            cursor.execute("SHOW IMPORTED KEYS IN DATABASE")
            names = [d[0].lower() for d in cursor.description]
            rows = [dict(zip(names, r, strict=True)) for r in cursor.fetchall()]
        finally:
            cursor.close()
        by_name: dict[str, list[dict]] = {}
        for r in rows:
            by_name.setdefault(r["fk_name"], []).append(r)
        out = []
        for name, cols in by_name.items():
            if len(cols) != 1:
                continue
            r = cols[0]
            out.append(ForeignKey(f"{r['fk_database_name']}.{r['fk_schema_name']}.{r['fk_table_name']}".lower(),
                                  r["fk_column_name"],
                                  f"{r['pk_database_name']}.{r['pk_schema_name']}.{r['pk_table_name']}".lower(),
                                  r["pk_column_name"], name))
        return out

    def test(self) -> TestResult:
        version, role, warehouse = self.query("SELECT CURRENT_VERSION(), CURRENT_ROLE(), CURRENT_WAREHOUSE()")[0]
        (count,) = self.query("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
                              "WHERE TABLE_SCHEMA <> 'INFORMATION_SCHEMA'")[0]
        if not count:
            return TestResult(False, f"Connected as role {role}, but it can see no tables in "
                                     f"{self.settings.get('database')}. Grant USAGE and SELECT to this role.")
        return TestResult(True, f"Connected to Snowflake {version} as {role}. {count} tables visible.",
                          {"version": str(version), "role": str(role), "warehouse": str(warehouse or ""),
                           "tables_visible": str(count)})


def _der(pem: str, passphrase: str | None) -> bytes:
    from cryptography.hazmat.primitives import serialization

    key = serialization.load_pem_private_key(pem.encode(), password=passphrase.encode() if passphrase else None)
    return key.private_bytes(encoding=serialization.Encoding.DER, format=serialization.PrivateFormat.PKCS8,
                             encryption_algorithm=serialization.NoEncryption())
