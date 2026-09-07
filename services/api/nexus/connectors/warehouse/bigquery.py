"""BigQuery warehouse connector.

BigQuery scopes ``INFORMATION_SCHEMA.COLUMNS`` to a dataset, but exposes a
region-wide view at ``region-<region>.INFORMATION_SCHEMA.COLUMNS`` that covers
every dataset in the project. The connector uses the region-wide form so one
connection observes a whole project rather than needing one per dataset.

Requires the ``google-cloud-bigquery`` extra.
"""

from __future__ import annotations

import json
from typing import Any

from nexus.connectors.spec import (
    Category,
    ConnectionField,
    ConnectionTestResult,
    ConnectorSpec,
    FieldType,
)
from nexus.connectors.warehouse.base import SqlWarehouseConnector

SYSTEM = "bigquery"

# BigQuery reports the catalog as the project id and the schema as the dataset.
# Views live in the same INFORMATION_SCHEMA, so no table_type join is needed.
_COLUMNS_QUERY_TEMPLATE = """
SELECT table_catalog,
       table_schema,
       table_name,
       column_name,
       data_type,
       is_nullable
  FROM `{project}.region-{region}.INFORMATION_SCHEMA.COLUMNS`
 ORDER BY table_schema, table_name, ordinal_position
"""

SPEC = ConnectorSpec(
    id=SYSTEM,
    name="BigQuery",
    category=Category.WAREHOUSE,
    description="Read schema history and job history; compile pipelines onto BigQuery.",
    driver_package="google-cloud-bigquery",
    docs_url="https://cloud.google.com/bigquery/docs/information-schema-columns",
    verified=False,
    fields=(
        ConnectionField(
            name="project",
            label="Project ID",
            placeholder="my-analytics-project",
            help="The GCP project whose datasets Nexus should observe.",
        ),
        ConnectionField(
            name="region",
            label="Region",
            default="us",
            placeholder="us",
            help="Region of the datasets, e.g. us, eu, europe-west2. "
            "Must match where the data lives, not where you are.",
        ),
        ConnectionField(
            name="service_account_json",
            label="Service account key (JSON)",
            type=FieldType.TEXTAREA,
            help="A key for a service account with roles/bigquery.metadataViewer "
            "and roles/bigquery.jobUser.",
        ),
    ),
)


def connect(config: dict[str, Any]) -> Any:
    """Open a BigQuery DB-API connection from a validated configuration."""
    try:
        from google.cloud import bigquery
        from google.cloud.bigquery import dbapi
        from google.oauth2 import service_account
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise RuntimeError(
            "the BigQuery driver is not installed; add the 'bigquery' extra"
        ) from exc

    try:
        info = json.loads(config["service_account_json"])
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"the service account key is not valid JSON: {exc}") from exc

    credentials = service_account.Credentials.from_service_account_info(info)
    client = bigquery.Client(project=config["project"], credentials=credentials)
    return dbapi.Connection(client)


class BigQueryConnector(SqlWarehouseConnector):
    """Reads schema state from a live BigQuery project."""

    system = SYSTEM

    def __init__(
        self,
        connection: Any,
        project: str,
        region: str = "us",
        database_label: str | None = None,
    ) -> None:
        super().__init__(connection, database_label)
        self._project = project
        self._region = region

    def _columns_query(self) -> tuple[str, Any]:
        return (
            _COLUMNS_QUERY_TEMPLATE.format(project=self._project, region=self._region),
            None,
        )


def test_connection(config: dict[str, Any]) -> ConnectionTestResult:
    """Probe a BigQuery configuration by reading the region-wide catalog."""
    project = config.get("project", "")
    region = config.get("region") or "us"

    try:
        connection = connect(config)
    except Exception as exc:  # noqa: BLE001
        return ConnectionTestResult.failure(_clean(exc))

    try:
        cursor = connection.cursor()
        cursor.execute(
            f"SELECT COUNT(DISTINCT CONCAT(table_schema, '.', table_name)) "
            f"FROM `{project}.region-{region}.INFORMATION_SCHEMA.TABLES`"
        )
        (table_count,) = cursor.fetchone()
        cursor.close()
    except Exception as exc:  # noqa: BLE001
        message = _clean(exc)
        if "was not found" in message.lower() or "not found" in message.lower():
            message += (
                f" — check that region '{region}' is where the datasets actually live."
            )
        return ConnectionTestResult.failure(message)
    finally:
        connection.close()

    if not table_count:
        return ConnectionTestResult.failure(
            f"Connected to {project}, but no tables are visible in region '{region}'. "
            "Check the region and that the service account has "
            "roles/bigquery.metadataViewer."
        )
    return ConnectionTestResult.success(
        f"Connected to BigQuery project {project}",
        project=project,
        region=region,
        tables_visible=str(table_count),
    )


def _clean(exc: Exception) -> str:
    """Render a driver error without leaking the configuration back to the user."""
    text = str(exc).strip().splitlines()[0] if str(exc).strip() else exc.__class__.__name__
    return text[:300]
