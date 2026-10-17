"""Warehouse connectors. Each kind declares its settings (spec) and reads metadata."""

from nexus.connectors.base import ConnectorError, Warehouse
from nexus.connectors.databricks import Databricks
from nexus.connectors.platforms import BigQuery, MySql, Oracle, Redshift, SapHana, SqlServer, Teradata
from nexus.connectors.postgres import Postgres
from nexus.connectors.snowflake import Snowflake

# In the order people choose them: the most common enterprise platforms first.
KINDS: dict[str, type[Warehouse]] = {c.spec.kind: c for c in (
    Snowflake, Databricks, SqlServer, Oracle, BigQuery, Redshift, SapHana, Postgres, Teradata, MySql)}

__all__ = ["KINDS", "ConnectorError", "Warehouse"]
