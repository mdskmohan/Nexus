"""Snowflake warehouse connector.

Reads schema state from ``INFORMATION_SCHEMA.COLUMNS``. Snowflake scopes that
view to a single database, so the connector is configured per database rather
than per account — a customer with several analytics databases configures one
connection each, which also keeps credential scope tight.

Requires the ``snowflake-connector-python`` extra.
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

SYSTEM = "snowflake"

#: Snowflake's own metadata, present in every database.
SYSTEM_SCHEMAS = ("INFORMATION_SCHEMA",)

# Snowflake uppercases unquoted identifiers, so the exclusion compares uppercase.
_COLUMNS_QUERY = """
SELECT c.TABLE_CATALOG,
       c.TABLE_SCHEMA,
       c.TABLE_NAME,
       c.COLUMN_NAME,
       c.DATA_TYPE,
       c.IS_NULLABLE
  FROM INFORMATION_SCHEMA.COLUMNS AS c
  JOIN INFORMATION_SCHEMA.TABLES AS t
    ON t.TABLE_CATALOG = c.TABLE_CATALOG
   AND t.TABLE_SCHEMA  = c.TABLE_SCHEMA
   AND t.TABLE_NAME    = c.TABLE_NAME
 WHERE c.TABLE_SCHEMA NOT IN ('INFORMATION_SCHEMA')
   AND t.TABLE_TYPE IN ('BASE TABLE', 'VIEW')
 ORDER BY c.TABLE_SCHEMA, c.TABLE_NAME, c.ORDINAL_POSITION
"""

SPEC = ConnectorSpec(
    id=SYSTEM,
    name="Snowflake",
    category=Category.WAREHOUSE,
    description="Read schema history and query history; compile pipelines onto Snowflake.",
    driver_package="snowflake-connector-python",
    docs_url="https://docs.snowflake.com/en/user-guide/admin-account-identifier",
    verified=False,
    fields=(
        ConnectionField(
            name="account",
            label="Account identifier",
            help="From your Snowflake URL, e.g. xy12345.eu-west-1 in "
            "xy12345.eu-west-1.snowflakecomputing.com",
            placeholder="xy12345.eu-west-1",
        ),
        ConnectionField(name="user", label="User", placeholder="NEXUS_SVC"),
        ConnectionField(
            name="password",
            label="Password",
            type=FieldType.SECRET,
            required=False,
            help="Leave blank if using a private key instead.",
        ),
        ConnectionField(
            name="private_key",
            label="Private key (PEM)",
            type=FieldType.TEXTAREA,
            required=False,
            help="Key-pair authentication. Preferred over a password for service users.",
        ),
        ConnectionField(
            name="private_key_passphrase",
            label="Private key passphrase",
            type=FieldType.SECRET,
            required=False,
        ),
        ConnectionField(name="warehouse", label="Warehouse", placeholder="COMPUTE_WH"),
        ConnectionField(name="database", label="Database", placeholder="ANALYTICS"),
        ConnectionField(
            name="role",
            label="Role",
            required=False,
            help="A read-only role is sufficient for observation.",
            placeholder="NEXUS_READONLY",
        ),
    ),
)


def connect(config: dict[str, Any]) -> Any:
    """Open a Snowflake connection from a validated configuration."""
    try:
        import snowflake.connector
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise RuntimeError(
            "the Snowflake driver is not installed; add the 'snowflake' extra"
        ) from exc

    params: dict[str, Any] = {
        "account": config["account"],
        "user": config["user"],
        "warehouse": config.get("warehouse"),
        "database": config.get("database"),
        # Nexus observes; it must never hold a transaction open on a customer
        # warehouse, and autocommit keeps read sessions from doing so.
        "autocommit": True,
        "client_session_keep_alive": False,
    }
    if role := config.get("role"):
        params["role"] = role

    if key := config.get("private_key"):
        params["private_key"] = _load_private_key(key, config.get("private_key_passphrase"))
    else:
        params["password"] = config.get("password")

    return snowflake.connector.connect(**params)


def _load_private_key(pem: str, passphrase: str | None) -> bytes:
    """Deserialise a PEM private key into the DER form the driver expects."""
    from cryptography.hazmat.primitives import serialization

    key = serialization.load_pem_private_key(
        pem.encode(),
        password=passphrase.encode() if passphrase else None,
    )
    return key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


class SnowflakeConnector(SqlWarehouseConnector):
    """Reads schema state from a live Snowflake database."""

    system = SYSTEM

    def _columns_query(self) -> tuple[str, Any]:
        return _COLUMNS_QUERY, None


def test_connection(config: dict[str, Any]) -> ConnectionTestResult:
    """Probe a Snowflake configuration by actually reading its catalog.

    Reads a table count rather than running ``SELECT 1`` so a pass proves the
    role can genuinely see the customer's objects — the common failure is
    credentials that authenticate fine but grant no visibility.
    """
    try:
        connection = connect(config)
    except Exception as exc:  # noqa: BLE001 - driver raises many types
        return ConnectionTestResult.failure(_clean(exc))

    try:
        with connection.cursor() as cur:
            cur.execute("SELECT CURRENT_VERSION(), CURRENT_ROLE(), CURRENT_WAREHOUSE()")
            version, role, warehouse = cur.fetchone()
            cur.execute(
                "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_SCHEMA <> 'INFORMATION_SCHEMA'"
            )
            (table_count,) = cur.fetchone()
    except Exception as exc:  # noqa: BLE001
        return ConnectionTestResult.failure(_clean(exc))
    finally:
        connection.close()

    if not table_count:
        return ConnectionTestResult.failure(
            f"Connected as role {role}, but it can see no tables in "
            f"{config.get('database')}. Grant USAGE and SELECT to this role."
        )
    return ConnectionTestResult.success(
        f"Connected to Snowflake {version} as {role}",
        version=str(version),
        role=str(role),
        warehouse=str(warehouse or ""),
        tables_visible=str(table_count),
    )


def _clean(exc: Exception) -> str:
    """Render a driver error without leaking the configuration back to the user."""
    text = str(exc).strip().splitlines()[0] if str(exc).strip() else exc.__class__.__name__
    return text[:300]
