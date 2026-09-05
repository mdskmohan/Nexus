"""The reference pipeline, orchestrated for real.

This is the DAG Nexus's connectors are developed against. It genuinely runs dbt
against Postgres, so the Airflow API returns real run state and the OpenLineage
provider emits real events.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

# dbt lives in its own virtualenv; see stack/Dockerfile.airflow.
DBT = "cd /opt/airflow/dbt && DBT_PROFILES_DIR=/opt/airflow/dbt /opt/dbt/bin/dbt"

with DAG(
    dag_id="customer_360",
    description="Unified customer dimension from Salesforce and application Postgres",
    start_date=datetime(2026, 9, 1),
    schedule="0 6 * * *",
    catchup=False,
    max_active_runs=1,
    default_args={"owner": "data-platform", "retries": 1,
                  "retry_delay": timedelta(minutes=5)},
    tags=["nexus", "reference"],
) as dag:
    stage = BashOperator(
        task_id="dbt_run_staging",
        bash_command=f"{DBT} run --select staging",
    )
    marts = BashOperator(
        task_id="dbt_run_marts",
        bash_command=f"{DBT} run --select marts",
    )
    test = BashOperator(
        task_id="dbt_test",
        bash_command=f"{DBT} test",
    )

    stage >> marts >> test
