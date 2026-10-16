"""Warehouse connectors. Each kind declares its settings (spec) and reads metadata."""

from nexus.connectors.base import ConnectorError, Warehouse
from nexus.connectors.databricks import Databricks
from nexus.connectors.postgres import Postgres
from nexus.connectors.snowflake import Snowflake

KINDS: dict[str, type[Warehouse]] = {"snowflake": Snowflake, "databricks": Databricks, "postgres": Postgres}

__all__ = ["KINDS", "ConnectorError", "Warehouse"]
