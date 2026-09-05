"""Closed vocabularies used across the IR.

These are deliberately small. A value belongs here only when the compiler or the
diagnosis engine has to branch on it; descriptive metadata stays as free text.
"""

from enum import StrEnum


class Materialization(StrEnum):
    """How a model is physically persisted in the warehouse."""

    TABLE = "table"
    VIEW = "view"
    INCREMENTAL = "incremental"
    EPHEMERAL = "ephemeral"


class LoadStrategy(StrEnum):
    """How new rows are reconciled with existing ones on each run."""

    FULL_REFRESH = "full_refresh"
    APPEND = "append"
    MERGE = "merge"
    SNAPSHOT = "snapshot"


class SourceKind(StrEnum):
    """The class of system a source reads from.

    Determines which ingestion mechanism the compiler emits.
    """

    SAAS = "saas"
    DATABASE = "database"
    OBJECT_STORE = "object_store"
    STREAM = "stream"


class Criticality(StrEnum):
    """Business importance, used for impact analysis and policy gating."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ConsumerKind(StrEnum):
    """What sits downstream of a pipeline and will notice when it breaks."""

    DASHBOARD = "dashboard"
    REVERSE_ETL = "reverse_etl"
    EXPORT = "export"
    ML_FEATURE = "ml_feature"


class Warehouse(StrEnum):
    """Supported compile targets for storage and compute."""

    SNOWFLAKE = "snowflake"
    DATABRICKS = "databricks"
    BIGQUERY = "bigquery"
    POSTGRES = "postgres"


class Orchestrator(StrEnum):
    """Supported compile targets for scheduling."""

    AIRFLOW = "airflow"
    DAGSTER = "dagster"


class Confidence(StrEnum):
    """How much we trust a field on a lifted spec.

    ``DECLARED`` means a human or the design agent stated it. The others describe
    how far we had to reach when reconstructing a spec from an existing pipeline;
    the diagnosis engine weights evidence accordingly.
    """

    DECLARED = "declared"
    PARSED = "parsed"
    INFERRED = "inferred"
