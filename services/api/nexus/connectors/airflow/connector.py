"""Airflow connector.

Supplies exactly what dbt cannot: when a pipeline runs, whether it succeeded, and
which task failed. A graph built from dbt alone is structurally complete and
operationally blind; this is what makes it able to answer "what happened".

Emits DAG and task nodes, EXECUTES edges from task to DAG, and DEPENDS_ON edges
between tasks reconstructed from each task's downstream ids.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from nexus.connectors.airflow.client import AirflowClient
from nexus.connectors.base import ConnectorResult
from nexus.connectors.spec import (
    Category,
    ConnectionField,
    ConnectionTestResult,
    ConnectorSpec,
    FieldType,
)
from nexus.graph.entities import Edge, EdgeKind, Node, NodeKind

SYSTEM = "airflow"

#: Airflow task states that mean the task did not complete its work.
FAILED_STATES = frozenset({"failed", "upstream_failed"})


def _namespaced(*parts: str) -> str:
    return f"{SYSTEM}:" + ".".join(parts)


def _parse_time(raw: str | None) -> datetime | None:
    """Parse an Airflow timestamp, tolerating the trailing Z form."""
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


@dataclass(frozen=True, slots=True)
class TaskFailure:
    """One failed task instance, with everything needed to open an investigation."""

    dag_id: str
    run_id: str
    task_id: str
    state: str
    try_number: int
    started_at: datetime | None
    ended_at: datetime | None

    @property
    def node_id(self) -> str:
        return _namespaced(self.dag_id, self.task_id)


class AirflowConnector:
    """Reads DAG structure and run history from a live Airflow deployment."""

    system = SYSTEM

    def __init__(self, client: AirflowClient, runs_per_dag: int = 25) -> None:
        self._client = client
        self._runs_per_dag = runs_per_dag

    def collect(self) -> ConnectorResult:
        """Emit every DAG, its tasks, and the dependency structure between them."""
        result = ConnectorResult()

        for dag in self._client.dags():
            dag_id = dag.get("dag_id")
            if not dag_id:
                continue

            schedule = dag.get("schedule_interval") or {}
            attributes = {
                "is_paused": str(bool(dag.get("is_paused"))).lower(),
                "is_active": str(bool(dag.get("is_active"))).lower(),
                "owners": ",".join(dag.get("owners") or []),
                "tags": ",".join(t.get("name", "") for t in dag.get("tags") or []),
            }
            # A paused DAG that "has not run" is not an incident, so the schedule
            # and paused flag together decide whether silence is suspicious.
            if isinstance(schedule, dict) and schedule.get("value"):
                attributes["schedule"] = str(schedule["value"])
            if description := dag.get("description"):
                attributes["description"] = str(description)

            result.nodes.append(
                Node(
                    id=_namespaced(dag_id),
                    kind=NodeKind.DAG,
                    name=dag_id,
                    system=SYSTEM,
                    attributes=attributes,
                )
            )
            self._collect_tasks(dag_id, result)

        if not result.nodes:
            result.warnings.append(
                "Airflow reported no DAGs; the deployment may be empty or the role "
                "may lack permission to list them"
            )
        return result

    def _collect_tasks(self, dag_id: str, result: ConnectorResult) -> None:
        """Emit task nodes and rebuild the DAG's internal dependency edges."""
        try:
            tasks = self._client.tasks(dag_id)
        except Exception as exc:  # noqa: BLE001 - one bad DAG must not lose the rest
            result.warnings.append(f"could not read tasks for DAG {dag_id}: {exc}")
            return

        known = {t.get("task_id") for t in tasks}
        for task in tasks:
            task_id = task.get("task_id")
            if not task_id:
                continue

            result.nodes.append(
                Node(
                    id=_namespaced(dag_id, task_id),
                    kind=NodeKind.TASK,
                    name=task_id,
                    system=SYSTEM,
                    attributes={
                        "dag_id": dag_id,
                        "operator": str(task.get("class_ref", {}).get("class_name", "")),
                        "retries": str(int(task.get("retries") or 0)),
                    },
                )
            )
            result.edges.append(
                Edge(
                    source=_namespaced(dag_id, task_id),
                    target=_namespaced(dag_id),
                    kind=EdgeKind.EXECUTES,
                )
            )

            for downstream in task.get("downstream_task_ids") or []:
                if downstream not in known:
                    result.warnings.append(
                        f"task {dag_id}.{task_id} lists unknown downstream {downstream!r}"
                    )
                    continue
                result.edges.append(
                    Edge(
                        source=_namespaced(dag_id, task_id),
                        target=_namespaced(dag_id, downstream),
                        kind=EdgeKind.DEPENDS_ON,
                    )
                )

    def recent_failures(self, dag_id: str) -> list[TaskFailure]:
        """Failed task instances across recent runs, newest run first.

        This is the trigger for an investigation: something failed, here is
        precisely which task and which attempt, so the log can be fetched.
        """
        failures: list[TaskFailure] = []
        for run in self._client.dag_runs(dag_id, limit=self._runs_per_dag):
            run_id = run.get("dag_run_id")
            if not run_id or run.get("state") != "failed":
                continue
            for ti in self._client.task_instances(dag_id, run_id):
                if ti.get("state") not in FAILED_STATES:
                    continue
                failures.append(
                    TaskFailure(
                        dag_id=dag_id,
                        run_id=run_id,
                        task_id=str(ti.get("task_id", "")),
                        state=str(ti.get("state", "")),
                        try_number=int(ti.get("try_number") or 1),
                        started_at=_parse_time(ti.get("start_date")),
                        ended_at=_parse_time(ti.get("end_date")),
                    )
                )
        return failures

    def last_run_state(self, dag_id: str) -> dict[str, Any] | None:
        """The most recent run, or None if the DAG exists but has never run.

        Airflow's dagRuns endpoint returns an empty list for a DAG that does not
        exist, which would make a deleted pipeline indistinguishable from an idle
        one. Those are different facts — a deleted pipeline is an incident and an
        idle one may not be — so existence is confirmed before reporting None.
        The extra request is only paid when there are no runs.
        """
        runs = self._client.dag_runs(dag_id, limit=1)
        if runs:
            return runs[0]
        self._client.dag(dag_id)  # raises AirflowError(404) if it does not exist
        return None


SPEC = ConnectorSpec(
    id=SYSTEM,
    name="Apache Airflow",
    category=Category.ORCHESTRATION,
    description="Read DAG schedules, run state and task logs from a self-hosted Airflow.",
    docs_url="https://airflow.apache.org/docs/apache-airflow/stable/stable-rest-api-ref.html",
    verified=True,
    fields=(
        ConnectionField(
            name="base_url",
            label="Airflow URL",
            placeholder="https://airflow.internal",
            help="The webserver's base URL, without /api/v1.",
        ),
        ConnectionField(name="username", label="Username", placeholder="nexus"),
        ConnectionField(name="password", label="Password", type=FieldType.SECRET),
    ),
)


def test_connection(config: dict[str, Any]) -> ConnectionTestResult:
    """Probe an Airflow configuration by reading health and listing DAGs.

    Health alone is not enough: a webserver can be healthy while the API auth
    backend rejects every request, so this also lists DAGs.
    """
    client = AirflowClient(
        config["base_url"], config["username"], config["password"], timeout=10.0
    )
    try:
        health = client.health()
        dags = client.dags()
    except Exception as exc:  # noqa: BLE001
        return ConnectionTestResult.failure(str(exc)[:300])
    finally:
        client.close()

    scheduler = (health.get("scheduler") or {}).get("status", "unknown")
    if scheduler != "healthy":
        return ConnectionTestResult.failure(
            f"Connected, but the Airflow scheduler reports '{scheduler}'. "
            "Run state will be stale until it recovers."
        )
    if not dags:
        return ConnectionTestResult.failure(
            "Connected, but no DAGs are visible. Check the user's role has Viewer "
            "permission on DAGs."
        )
    return ConnectionTestResult.success(
        f"Connected to Airflow: {len(dags)} DAG(s) visible",
        scheduler=scheduler,
        dags_visible=str(len(dags)),
        metadatabase=(health.get("metadatabase") or {}).get("status", "unknown"),
    )
