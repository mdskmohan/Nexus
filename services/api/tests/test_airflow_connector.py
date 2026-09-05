"""Integration tests for the Airflow connector.

These run against the real Airflow in the local stack — its real REST API, its
real DAG, and its real run history. They skip when the stack is down.
"""

from __future__ import annotations

import pytest

from nexus.connectors.airflow import AirflowClient, AirflowConnector, AirflowError
from nexus.graph.entities import EdgeKind, NodeKind
from tests.conftest_stack import (
    AIRFLOW_AUTH,
    AIRFLOW_URL,
    SKIP_REASON,
    airflow_available,
)

pytestmark = pytest.mark.skipif(not airflow_available(), reason=SKIP_REASON)

DAG_ID = "customer_360"


@pytest.fixture
def client():
    with AirflowClient(AIRFLOW_URL, *AIRFLOW_AUTH) as c:
        yield c


@pytest.fixture
def connector(client):
    return AirflowConnector(client)


@pytest.fixture
def result(connector):
    return connector.collect()


class TestClient:
    def test_health_reports_scheduler_and_metadatabase(self, client) -> None:
        health = client.health()
        assert health["metadatabase"]["status"] == "healthy"
        assert health["scheduler"]["status"] == "healthy"

    def test_bad_credentials_are_reported_clearly(self) -> None:
        with AirflowClient(AIRFLOW_URL, "nexus", "wrong-password") as bad:
            with pytest.raises(AirflowError, match="rejected the credentials"):
                bad.dags()

    def test_unreachable_host_is_reported_clearly(self) -> None:
        with AirflowClient("http://127.0.0.1:1", "u", "p", timeout=1.0) as dead:
            with pytest.raises(AirflowError, match="could not reach Airflow"):
                dead.dags()

    def test_unknown_dag_is_reported_clearly(self, client) -> None:
        with pytest.raises(AirflowError, match="404"):
            client.tasks("no_such_dag")


class TestStructure:
    def test_dag_is_recovered_with_its_schedule(self, result) -> None:
        """The schedule is what makes 'this has not run' judgeable as an incident."""
        dag = next(n for n in result.nodes if n.kind is NodeKind.DAG)
        assert dag.name == DAG_ID
        assert dag.attributes["schedule"] == "0 6 * * *"
        assert dag.attributes["is_paused"] == "false"
        assert dag.attributes["owners"] == "data-platform"

    def test_tasks_are_recovered(self, result) -> None:
        tasks = {n.name for n in result.nodes if n.kind is NodeKind.TASK}
        assert tasks == {"dbt_run_staging", "dbt_run_marts", "dbt_test"}

    def test_task_operator_and_retries_are_typed_cleanly(self, result) -> None:
        """Airflow reports retries as a float; evidence showing '1.0' reads as a bug."""
        task = next(n for n in result.nodes if n.name == "dbt_run_marts")
        assert task.attributes["operator"] == "BashOperator"
        assert task.attributes["retries"] == "1"

    def test_execution_edges_link_tasks_to_their_dag(self, result) -> None:
        executes = {
            e.source for e in result.edges if e.kind is EdgeKind.EXECUTES
        }
        assert len(executes) == 3
        assert all(
            e.target == f"airflow:{DAG_ID}"
            for e in result.edges
            if e.kind is EdgeKind.EXECUTES
        )

    def test_dependency_order_is_reconstructed(self, result) -> None:
        deps = {
            (e.source.split(".")[-1], e.target.split(".")[-1])
            for e in result.edges
            if e.kind is EdgeKind.DEPENDS_ON
        }
        assert ("dbt_run_staging", "dbt_run_marts") in deps
        assert ("dbt_run_marts", "dbt_test") in deps

    def test_node_ids_are_namespaced(self, result) -> None:
        assert all(n.id.startswith("airflow:") for n in result.nodes)

    def test_clean_deployment_produces_no_warnings(self, result) -> None:
        assert result.warnings == []


class TestRunHistory:
    def test_last_run_state_is_available(self, connector) -> None:
        run = connector.last_run_state(DAG_ID)
        assert run is not None
        assert run["state"] in {"success", "failed", "running", "queued"}

    def test_recent_failures_are_typed(self, connector) -> None:
        """Every failure must carry enough to fetch its log without more lookups."""
        for failure in connector.recent_failures(DAG_ID):
            assert failure.dag_id == DAG_ID
            assert failure.task_id
            assert failure.run_id
            assert failure.try_number >= 1
            assert failure.node_id.startswith("airflow:")

    def test_unknown_dag_raises_rather_than_reporting_no_runs(self, connector) -> None:
        """A missing DAG and a DAG that has never run are different facts.

        Collapsing them would let a deleted pipeline look merely idle.
        """
        with pytest.raises(AirflowError, match="404"):
            connector.last_run_state("no_such_dag_at_all")
