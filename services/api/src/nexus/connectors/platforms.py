"""SQL Server, Oracle, MySQL, BigQuery, Redshift, SAP HANA and Teradata.

Each is a SQLAlchemy dialect plus the vendor's (or the standard) driver, as in
OpenMetadata: the settings mirror OpenMetadata's connection definitions for the
same platform, and the URL is built the way OpenMetadata builds it. All of them
only read.
"""

import json
import ssl
from typing import Any

from sqlalchemy.engine import URL

from nexus.connectors.base import ConnectorError
from nexus.connectors.spec import FILTERS, Field, Spec
from nexus.connectors.sqla import SqlAlchemyWarehouse


def _port(settings: dict, default: int) -> int:
    value = settings.get("port") or str(default)
    if not value.isdigit():
        raise ConnectorError("Port must be a number.")
    return int(value)


# SQL Server, Azure SQL, Azure Synapse, Microsoft Fabric -------------------------------

class SqlServer(SqlAlchemyWarehouse):
    spec = Spec(
        kind="sqlserver",
        verified=True,
        name="SQL Server / Azure SQL / Fabric",
        description="SQL Server 2016 or later, Azure SQL Database and Managed Instance, Synapse dedicated pools and "
                    "Microsoft Fabric. Signs in with a SQL login or Microsoft Entra ID.",
        docs_url="https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server",
        fields=(
            Field("host", "Server", placeholder="myserver.database.windows.net"),
            Field("port", "Port", default="1433"),
            Field("database", "Database", placeholder="analytics"),
            Field("driver", "Driver", required=False, default="pymssql",
                  options=("pymssql", "ODBC Driver 18 for SQL Server"),
                  help="pymssql needs nothing installed. Microsoft Entra sign-in (needed for Fabric) uses the "
                       "ODBC driver, which must be installed on the Nexus server."),
            Field("authentication", "Sign-in", required=False, default="sql",
                  options=("sql", "entra_service_principal", "entra_password"),
                  help="sql: a SQL login. entra_service_principal: user is the application (client) id and "
                       "password its secret. entra_password: a Microsoft Entra user."),
            Field("user", "User", placeholder="nexus_reader"),
            Field("password", "Password", secret=True),
            *FILTERS,
        ),
    )
    dialect = "tsql"
    system_schemas = frozenset({"sys", "INFORMATION_SCHEMA", "guest", "db_owner", "db_accessadmin",
                                "db_securityadmin", "db_ddladmin", "db_backupoperator", "db_datareader",
                                "db_datawriter", "db_denydatareader", "db_denydatawriter"})
    extra_checks = {"List databases": "SELECT name FROM sys.databases"}

    def _odbc(self) -> bool:
        return (self.settings.get("driver") or "pymssql") != "pymssql"

    def url(self) -> URL:
        s, auth = self.settings, self.settings.get("authentication") or "sql"
        if not self._odbc():
            if auth != "sql":
                raise ConnectorError("Microsoft Entra sign-in needs the ODBC driver. Choose it under Driver.")
            return URL.create("mssql+pymssql", username=s["user"], password=self.secrets.get("password"),
                              host=s["host"], port=_port(s, 1433), database=s["database"])
        parts = {"DRIVER": f"{{{s['driver']}}}", "SERVER": f"{s['host']},{_port(s, 1433)}",
                 "DATABASE": s["database"], "UID": s["user"], "PWD": self.secrets.get("password", ""),
                 "Encrypt": "yes", "TrustServerCertificate": "no"}
        if auth == "entra_service_principal":
            parts["Authentication"] = "ActiveDirectoryServicePrincipal"
        elif auth == "entra_password":
            parts["Authentication"] = "ActiveDirectoryPassword"
        odbc = ";".join(f"{k}={{{v}}}" if k in ("UID", "PWD") else f"{k}={v}" for k, v in parts.items())
        return URL.create("mssql+pyodbc", query={"odbc_connect": odbc})

    def connect_args(self) -> dict[str, Any]:
        return {} if self._odbc() else {"login_timeout": 20, "timeout": 120}

    def database_label(self) -> str:
        return self.settings["database"]


# Oracle --------------------------------------------------------------------------------

class Oracle(SqlAlchemyWarehouse):
    spec = Spec(
        kind="oracle",
        verified=True,
        name="Oracle",
        description="Oracle Database 12c or later, on premises, Exadata or Autonomous Database. Connects directly by "
                    "service name or SID; no Oracle client to install.",
        docs_url="https://python-oracledb.readthedocs.io/en/latest/user_guide/connection_handling.html",
        fields=(
            Field("host", "Host", placeholder="db.internal"),
            Field("port", "Port", default="1521"),
            Field("connection_type", "Connect by", required=False, default="service_name",
                  options=("service_name", "sid")),
            Field("service", "Service name or SID", placeholder="ORCLPDB1"),
            Field("user", "User", placeholder="NEXUS_READER"),
            Field("password", "Password", secret=True),
            *FILTERS,
        ),
    )
    dialect = "oracle"
    three_part_names = False
    check_access_sql = "SELECT 1 FROM DUAL"
    extra_checks = {"Read the table catalogue": "SELECT table_name FROM ALL_TABLES WHERE ROWNUM < 2"}
    # Schemas Oracle creates for itself (the ORACLE_MAINTAINED users of a standard install).
    system_schemas = frozenset({
        "anonymous", "appqossys", "audsys", "ctxsys", "dbsfwuser", "dbsnmp", "dgpdb_int", "dip", "dvf", "dvsys",
        "ggsys", "gsmadmin_internal", "gsmcatuser", "gsmrootuser", "gsmuser", "lbacsys", "mddata", "mdsys",
        "ojvmsys", "olapsys", "oracle_ocm", "orddata", "ordplugins", "ordsys", "outln", "remote_scheduler_agent",
        "si_informtn_schema", "sys", "sys$umf", "sysbackup", "sysdg", "syskm", "sysrac", "system", "wmsys",
        "xdb", "xs$null", "apex_public_user", "flows_files", "pdbadmin", "ggsharedcap", "vecsys", "baasys",
    })

    def url(self) -> URL:
        s = self.settings
        common = {"username": s["user"], "password": self.secrets.get("password"), "host": s["host"],
                  "port": _port(s, 1521)}
        if (s.get("connection_type") or "service_name") == "sid":
            return URL.create("oracle+oracledb", database=s["service"], **common)
        return URL.create("oracle+oracledb", query={"service_name": s["service"]}, **common)

    def connect_args(self) -> dict[str, Any]:
        return {"tcp_connect_timeout": 20}

    def database_label(self) -> str:
        return self.settings["service"].lower()

    def schemas(self) -> list[str]:
        # Oracle lists every user as a schema; keep those that own something we can read.
        owners = {r[0].lower() for r in self.query("SELECT DISTINCT owner FROM ALL_TABLES UNION "
                                                   "SELECT DISTINCT owner FROM ALL_VIEWS")}
        return [s for s in super().schemas() if s.lower() in owners]


# MySQL and MariaDB ---------------------------------------------------------------------

class MySql(SqlAlchemyWarehouse):
    spec = Spec(
        kind="mysql",
        verified=True,
        name="MySQL",
        description="MySQL 5.7 or later, MariaDB, Amazon RDS and Aurora MySQL, and Azure Database for MySQL. Each "
                    "database is read as a schema.",
        fields=(
            Field("host", "Host", placeholder="db.internal"),
            Field("port", "Port", default="3306"),
            Field("user", "User", placeholder="nexus_reader"),
            Field("password", "Password", secret=True),
            Field("database", "Database", required=False, placeholder="analytics",
                  help="In MySQL a database is a schema. Leave blank to read every one the user can see."),
            Field("tls", "Encryption", required=False, default="preferred",
                  options=("preferred", "required", "verify")),
            *FILTERS,
        ),
    )
    dialect = "mysql"
    three_part_names = False
    system_schemas = frozenset({"information_schema", "mysql", "performance_schema", "sys"})

    def url(self) -> URL:
        s = self.settings
        return URL.create("mysql+pymysql", username=s["user"], password=self.secrets.get("password"),
                          host=s["host"], port=_port(s, 3306), database=s.get("database") or None)

    def connect_args(self) -> dict[str, Any]:
        args: dict[str, Any] = {"connect_timeout": 20, "read_timeout": 120}
        mode = self.settings.get("tls") or "preferred"
        if mode == "required":
            args["ssl"] = {"check_hostname": False, "verify_mode": ssl.CERT_NONE}
        elif mode == "verify":
            args["ssl"] = {"check_hostname": True, "verify_mode": ssl.CERT_REQUIRED}
        return args

    def database_label(self) -> str:
        return "mysql"

    def schemas(self) -> list[str]:
        if self.settings.get("database"):
            return [self.settings["database"]]
        return super().schemas()


# Google BigQuery -----------------------------------------------------------------------

class BigQuery(SqlAlchemyWarehouse):
    spec = Spec(
        kind="bigquery",
        name="Google BigQuery",
        description="Google BigQuery. Reads every dataset in one Google Cloud project as a schema, signing in with a "
                    "service account key.",
        docs_url="https://cloud.google.com/bigquery/docs/authentication/service-account-file",
        fields=(
            Field("project_id", "Project ID", placeholder="acme-analytics"),
            Field("credentials", "Service account key (JSON)", secret=True, multiline=True,
                  help="A key for a service account with BigQuery Data Viewer and BigQuery Job User."),
            Field("location", "Location", required=False, placeholder="US",
                  help="Where the datasets live, if not the US multi-region."),
            *FILTERS,
        ),
    )
    dialect = "bigquery"
    system_schemas = frozenset({"INFORMATION_SCHEMA"})

    def _key(self) -> dict:
        try:
            key = json.loads(self.secrets.get("credentials") or "")
        except json.JSONDecodeError as exc:
            raise ConnectorError("The service account key is not valid JSON.") from exc
        if key.get("type") != "service_account":
            raise ConnectorError("Paste the JSON key of a service account.")
        return key

    def url(self) -> URL:
        return URL.create("bigquery", host=self.settings["project_id"])

    def engine_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"credentials_info": self._key()}
        if self.settings.get("location"):
            kwargs["location"] = self.settings["location"]
        return kwargs

    def database_label(self) -> str:
        return self.settings["project_id"]


# Amazon Redshift -----------------------------------------------------------------------

class Redshift(SqlAlchemyWarehouse):
    spec = Spec(
        kind="redshift",
        name="Amazon Redshift",
        description="Amazon Redshift provisioned clusters and Redshift Serverless workgroups. Signs in with a database "
                    "user over SSL.",
        docs_url="https://docs.aws.amazon.com/redshift/latest/mgmt/python-configuration-options.html",
        fields=(
            Field("host", "Endpoint", placeholder="acme.abc123.eu-west-1.redshift.amazonaws.com"),
            Field("port", "Port", default="5439"),
            Field("database", "Database", placeholder="dev"),
            Field("user", "User", placeholder="nexus_reader"),
            Field("password", "Password", secret=True),
            Field("sslmode", "SSL", required=False, default="verify-ca",
                  options=("verify-ca", "verify-full", "disable")),
            *FILTERS,
        ),
    )
    dialect = "redshift"
    system_schemas = frozenset({"information_schema", "pg_catalog", "pg_internal", "pg_automv", "pg_auto_copy",
                                "pg_mv", "pg_s3", "catalog_history", "pg_toast"})
    extra_checks = {"List databases": "SELECT datname FROM pg_database"}

    def url(self) -> URL:
        s = self.settings
        return URL.create("redshift+redshift_connector", username=s["user"], password=self.secrets.get("password"),
                          host=s["host"], port=_port(s, 5439), database=s["database"])

    def connect_args(self) -> dict[str, Any]:
        mode = self.settings.get("sslmode") or "verify-ca"
        args: dict[str, Any] = {"timeout": 20}
        if mode == "disable":
            args["ssl"] = False
        else:
            args["ssl"], args["sslmode"] = True, mode
        return args

    def database_label(self) -> str:
        return self.settings["database"]


# SAP HANA ------------------------------------------------------------------------------

class SapHana(SqlAlchemyWarehouse):
    spec = Spec(
        kind="saphana",
        name="SAP HANA",
        description="SAP HANA Cloud and SAP HANA 2.0 on premises, including the database under SAP Datasphere. "
                    "Signs in with a database user over TLS.",
        docs_url="https://help.sap.com/docs/SAP_HANA_CLIENT",
        fields=(
            Field("host", "Host", placeholder="abc123.hana.prod-eu10.hanacloud.ondemand.com"),
            Field("port", "Port", default="443", help="443 for SAP HANA Cloud; 3NN15 or 3NN13 on premises."),
            Field("database", "Tenant database", required=False,
                  help="For a multi-tenant system on premises. Leave blank for SAP HANA Cloud."),
            Field("user", "User", placeholder="NEXUS_READER"),
            Field("password", "Password", secret=True),
            Field("encrypt", "Encryption", required=False, default="true", options=("true", "false")),
            *FILTERS,
        ),
    )
    dialect = "postgres"  # sqlglot has no HANA dialect; HANA accepts double-quoted names and LIMIT
    three_part_names = False
    check_access_sql = "SELECT 1 FROM DUMMY"
    system_schemas = frozenset({"SYS", "SYSTEM", "HANA_XS_BASE", "SAP_PA_APL", "UIS", "BROKER_PO_USER",
                                "BROKER_USER", "SAPDBCTRL", "SYS_DATABASES"})

    def url(self) -> URL:
        s = self.settings
        encrypt = (s.get("encrypt") or "true") == "true"
        return URL.create("hana", username=s["user"], password=self.secrets.get("password"), host=s["host"],
                          port=_port(s, 443), database=s.get("database") or None,
                          query={"encrypt": str(encrypt).lower(), "sslValidateCertificate": str(encrypt).lower()})

    def connect_args(self) -> dict[str, Any]:
        return {"connectTimeout": 20000}

    def database_label(self) -> str:
        return (self.settings.get("database") or "hana").lower()

    def schemas(self) -> list[str]:
        # _SYS_* schemas belong to HANA itself.
        return [s for s in super().schemas() if not s.upper().startswith("_SYS")]


# Teradata ------------------------------------------------------------------------------

class Teradata(SqlAlchemyWarehouse):
    spec = Spec(
        kind="teradata",
        name="Teradata",
        description="Teradata Vantage on premises, VantageCloud Enterprise and Lake. Reads each database as a schema; "
                    "signs in with TD2, LDAP or Kerberos.",
        docs_url="https://github.com/Teradata/python-driver#ConnectionParameters",
        fields=(
            Field("host", "Host", placeholder="tdprod.internal"),
            Field("port", "Port", default="1025"),
            Field("user", "User", placeholder="nexus_reader"),
            Field("password", "Password", secret=True),
            Field("logmech", "Sign-in mechanism", required=False, default="TD2",
                  options=("TD2", "LDAP", "TDNEGO", "KRB5", "JWT", "BROWSER")),
            Field("tmode", "Transaction mode", required=False, default="DEFAULT", options=("DEFAULT", "ANSI", "TERA")),
            Field("account", "Account", required=False),
            *FILTERS,
        ),
    )
    dialect = "teradata"
    three_part_names = False
    extra_checks = {"List databases": "SELECT TOP 1 DatabaseName FROM DBC.DatabasesV"}
    system_schemas = frozenset({
        "dbc", "crashdumps", "dbcmngr", "default", "external_ap", "extuser", "locklogshredder", "public",
        "sqlj", "sysadmin", "sys_calendar", "sysbar", "sysjdbc", "syslib", "sysspatial", "systemfe", "sysudtlib",
        "sysuif", "td_server_db", "td_sysfnlib", "td_sysgpl", "td_sysxml", "tdmaps", "tdpuser", "tdqcd",
        "tdstats", "tdwm", "td_analytics_db", "tdbcmgmt", "td_sysudtlib", "val", "all", "console",
        "td_mldb", "td_metric_svc", "tapidb", "tdmaplib", "gs_tables_db", "sas_sysfnlib",
    })

    def url(self) -> URL:
        s = self.settings
        query = {"dbs_port": str(_port(s, 1025)), "logmech": s.get("logmech") or "TD2",
                 "tmode": s.get("tmode") or "DEFAULT", "connect_timeout": "20000"}
        if s.get("account"):
            query["account"] = s["account"]
        return URL.create("teradatasql", username=s["user"], password=self.secrets.get("password"),
                          host=s["host"], query=query)

    def database_label(self) -> str:
        return "teradata"
