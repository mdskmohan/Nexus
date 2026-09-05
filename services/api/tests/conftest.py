"""Shared fixtures.

The ``customer_360`` fixture is the reference pipeline used across the suite and in
the compiler golden tests. Keep it realistic — it doubles as documentation of what a
well-formed spec looks like.
"""

from datetime import timedelta

import pytest

from nexus.ir.enums import (
    ConsumerKind,
    Criticality,
    LoadStrategy,
    Materialization,
    Orchestrator,
    SourceKind,
    Warehouse,
)
from nexus.ir.spec import (
    Column,
    CompileTarget,
    Consumer,
    FreshnessPolicy,
    Model,
    Ownership,
    PipelineSpec,
    Schedule,
    SchemaContract,
    Source,
)


@pytest.fixture
def customer_360() -> PipelineSpec:
    """A daily customer 360 built from Salesforce and application Postgres."""
    return PipelineSpec(
        id="customer_360",
        name="Customer 360",
        criticality=Criticality.HIGH,
        owner=Ownership(team="data-platform", oncall="@data-oncall"),
        target=CompileTarget(
            warehouse=Warehouse.SNOWFLAKE,
            orchestrator=Orchestrator.AIRFLOW,
            database="ANALYTICS",
            schema_name="MARTS",
        ),
        schedule=Schedule(cron="0 6 * * *", sla=timedelta(hours=2)),
        sources=(
            Source(
                id="salesforce_account",
                kind=SourceKind.SAAS,
                connector="fivetran",
                object_name="salesforce.account",
                freshness=FreshnessPolicy(
                    warn_after=timedelta(hours=6), error_after=timedelta(hours=24)
                ),
                contract=SchemaContract(
                    columns=(
                        Column(name="id", data_type="string", nullable=False),
                        Column(name="name", data_type="string"),
                    ),
                    primary_key=("id",),
                ),
            ),
            Source(
                id="app_users",
                kind=SourceKind.DATABASE,
                connector="fivetran",
                object_name="public.users",
            ),
        ),
        models=(
            Model(
                id="stg_accounts",
                sql="SELECT id AS customer_id, name FROM {{ ref('salesforce_account') }}",
                depends_on=("salesforce_account",),
                materialization=Materialization.VIEW,
            ),
            Model(
                id="stg_users",
                sql="SELECT id AS user_id, account_id FROM {{ ref('app_users') }}",
                depends_on=("app_users",),
                materialization=Materialization.VIEW,
            ),
            Model(
                id="dim_customer",
                sql=(
                    "SELECT a.customer_id, a.name, COUNT(u.user_id) AS user_count "
                    "FROM {{ ref('stg_accounts') }} a "
                    "LEFT JOIN {{ ref('stg_users') }} u ON u.account_id = a.customer_id "
                    "GROUP BY 1, 2"
                ),
                depends_on=("stg_accounts", "stg_users"),
                materialization=Materialization.INCREMENTAL,
                load_strategy=LoadStrategy.MERGE,
                contract=SchemaContract(
                    columns=(
                        Column(name="customer_id", data_type="string", nullable=False),
                        Column(name="name", data_type="string"),
                        Column(name="user_count", data_type="int64"),
                    ),
                    primary_key=("customer_id",),
                ),
            ),
        ),
        consumers=(
            Consumer(
                id="exec_dashboard",
                kind=ConsumerKind.DASHBOARD,
                name="Executive Overview",
                reads=("dim_customer",),
                owner="analytics",
            ),
        ),
    )
