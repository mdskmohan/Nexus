# Connectors

Nexus reads ten platforms, the ones enterprises use most. Every connector only reads: it lists schemas,
tables, views, columns, comments and declared foreign keys, and samples a few values when it checks a
suggested join. Credentials are encrypted per workspace and never returned.

| Platform | Driver | Proven against a real server |
|---|---|---|
| Snowflake | `snowflake-connector-python` | Not yet: needs an account |
| Databricks (Unity Catalog) | `databricks-sql-connector` | Not yet: needs a workspace |
| SQL Server, Azure SQL, Azure Synapse, Microsoft Fabric | `pymssql`, or `pyodbc` with ODBC Driver 18 for Microsoft Entra sign-in | **Yes**, SQL Server 2022 (`make warehouses`) |
| Oracle | `oracledb` (thin mode, no Oracle client) | **Yes**, Oracle Database 23ai Free |
| Google BigQuery | `sqlalchemy-bigquery` | Not yet: needs a project |
| Amazon Redshift | `redshift_connector` with `sqlalchemy-redshift` | Not yet: needs a cluster |
| SAP HANA | `hdbcli` with `sqlalchemy-hana` | Not yet: needs a system |
| PostgreSQL | `psycopg` | **Yes** |
| Teradata | `teradatasql` with `teradatasqlalchemy` | Not yet: needs a system |
| MySQL, MariaDB | `pymysql` | **Yes**, MySQL 8.4 |

## How they work

The approach follows OpenMetadata's database connectors (we read their open-source code to learn it; the
code here is our own):

- **One SQLAlchemy engine per connection**, built from the platform's own dialect and driver, with no
  connection pool and in autocommit mode where the dialect supports it, so reading the catalogue never holds
  a transaction or locks open.
- **The catalogue is read with SQLAlchemy's inspector**, in bulk where the dialect can (one query per schema
  rather than per table), falling back to one table at a time and skipping tables the user may not read.
  Snowflake, Databricks and PostgreSQL read `information_schema` directly in one query.
- **System schemas are skipped** per platform (for example `sys` on SQL Server, Oracle's own users, `DBC`
  on Teradata, `_SYS_*` on SAP HANA).
- **Schema filters** on every connection: comma-separated patterns to include or exclude, like
  OpenMetadata's filter patterns.
- **The connection test runs named steps**: check access, list schemas, list tables, list views, plus a
  platform-specific check (for example listing databases on SQL Server). Each step's result is shown.
- **Names keep the case the database stores**: dialects such as Oracle's report upper-case names in lower
  case, and Nexus converts them back before it quotes them.

## Testing locally

```bash
make warehouses                 # real MySQL 8.4, SQL Server 2022 and Oracle 23ai Free in Docker
cd services/api && uv run pytest tests/test_connectors.py
```

Each test loads the same small sales and CRM data into a real database and goes through the API: add the
connection, test it, read its tables, and check that Nexus finds the declared foreign key and the join that
only names and sampled values reveal. CI runs the same tests against the same databases.
