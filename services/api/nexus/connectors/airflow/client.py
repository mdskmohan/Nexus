"""Airflow REST API client.

Thin, read-only wrapper over the Airflow v1 REST API. It exists so the connector
can be tested against a real Airflow without the connector itself owning HTTP
concerns, and so credential handling stays in one place.

Read-only by construction: this client issues GET requests and nothing else.
Triggering or clearing a DAG is an *action*, and actions go through the policy
engine, not through a connector.
"""

from __future__ import annotations

from typing import Any

import httpx

from nexus.errors import NexusError


class AirflowError(NexusError):
    """The Airflow API was unreachable, refused the request, or returned nonsense."""


class AirflowClient:
    """Read-only client for one Airflow deployment."""

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        timeout: float = 10.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=f"{self._base_url}/api/v1",
            auth=(username, password),
            timeout=timeout,
            headers={"Accept": "application/json"},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> AirflowClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _get(self, path: str, **params: Any) -> dict[str, Any]:
        try:
            response = self._client.get(path, params=params or None)
        except httpx.HTTPError as exc:
            raise AirflowError(f"could not reach Airflow at {self._base_url}: {exc}") from exc

        if response.status_code == 401:
            raise AirflowError("Airflow rejected the credentials (401)")
        if response.status_code == 404:
            raise AirflowError(f"Airflow has no resource at {path} (404)")
        if response.status_code >= 400:
            raise AirflowError(
                f"Airflow returned {response.status_code} for {path}: {response.text[:200]}"
            )
        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise AirflowError(f"Airflow returned non-JSON for {path}") from exc
        if not isinstance(payload, dict):
            raise AirflowError(f"expected an object from {path}, got {type(payload).__name__}")
        return payload

    def _paginate(self, path: str, key: str, page_size: int = 100) -> list[dict[str, Any]]:
        """Collect every page of a list endpoint.

        Airflow caps page size server-side, and a customer with hundreds of DAGs
        would otherwise be silently truncated to the first page — a graph missing
        entities is worse than an error.
        """
        items: list[dict[str, Any]] = []
        offset = 0
        while True:
            payload = self._get(path, limit=page_size, offset=offset)
            batch = payload.get(key, [])
            items.extend(batch)
            total = payload.get("total_entries")
            offset += len(batch)
            if not batch or total is None or offset >= total:
                return items

    def health(self) -> dict[str, Any]:
        """Scheduler and metadatabase health. Used to distinguish 'down' from 'empty'."""
        try:
            response = self._client.get(f"{self._base_url}/health")
            response.raise_for_status()
            result: Any = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AirflowError(f"health check failed: {exc}") from exc
        return result if isinstance(result, dict) else {}

    def dags(self) -> list[dict[str, Any]]:
        """Every DAG known to this deployment, including paused ones."""
        return self._paginate("/dags", "dags")

    def tasks(self, dag_id: str) -> list[dict[str, Any]]:
        """Task definitions for a DAG, carrying downstream ids — the DAG's structure."""
        return self._get(f"/dags/{dag_id}/tasks").get("tasks", [])

    def dag(self, dag_id: str) -> dict[str, Any]:
        """One DAG's definition. Raises if the deployment has no such DAG."""
        return self._get(f"/dags/{dag_id}")

    def dag_runs(self, dag_id: str, limit: int = 25) -> list[dict[str, Any]]:
        """Most recent runs, newest first."""
        payload = self._get(
            f"/dags/{dag_id}/dagRuns",
            limit=limit,
            order_by="-execution_date",
        )
        return payload.get("dag_runs", [])

    def task_instances(self, dag_id: str, run_id: str) -> list[dict[str, Any]]:
        """Per-task outcome for one run — the evidence behind 'which step failed'."""
        payload = self._get(f"/dags/{dag_id}/dagRuns/{run_id}/taskInstances")
        return payload.get("task_instances", [])

    def task_log(self, dag_id: str, run_id: str, task_id: str, try_number: int = 1) -> str:
        """Raw log for one task attempt.

        This is where a SQL error message actually lives, so it is the source of
        the most specific evidence available for a failure.
        """
        response = self._client.get(
            f"/dags/{dag_id}/dagRuns/{run_id}/taskInstances/{task_id}/logs/{try_number}",
            params={"full_content": "true"},
            headers={"Accept": "text/plain"},
        )
        if response.status_code >= 400:
            raise AirflowError(
                f"could not read log for {dag_id}.{task_id} attempt {try_number}: "
                f"{response.status_code}"
            )
        return response.text
