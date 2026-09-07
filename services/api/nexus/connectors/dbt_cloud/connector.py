"""dbt Cloud connector.

dbt Cloud serves ``manifest.json`` as a run artifact, so this connector's job is
to fetch the manifest from the most recent successful run and hand it to the
existing manifest parser. The graph produced is identical to dbt Core's — the
difference is only how the artifact is obtained.

It additionally supplies what dbt Core cannot: job schedules and run history,
which on a dbt Cloud estate replaces what Airflow provides elsewhere.

Requires no extra driver; dbt Cloud is a REST API.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import httpx

from nexus.connectors.base import ConnectorResult
from nexus.connectors.dbt.manifest import DbtManifestConnector
from nexus.connectors.spec import (
    Category,
    ConnectionField,
    ConnectionTestResult,
    ConnectorSpec,
    FieldType,
)
from nexus.errors import NexusError

SYSTEM = "dbt_cloud"

SPEC = ConnectorSpec(
    id=SYSTEM,
    name="dbt Cloud",
    category=Category.TRANSFORMATION,
    description="Fetch the manifest, job schedules and run history from dbt Cloud.",
    docs_url="https://docs.getdbt.com/dbt-cloud/api-v2",
    verified=False,
    fields=(
        ConnectionField(
            name="access_url",
            label="Access URL",
            default="https://cloud.getdbt.com",
            help="Your dbt Cloud host. Regional and single-tenant accounts differ, "
            "e.g. https://emea.dbt.com",
            placeholder="https://cloud.getdbt.com",
        ),
        ConnectionField(
            name="account_id",
            label="Account ID",
            type=FieldType.NUMBER,
            help="The number in your dbt Cloud URL after /accounts/.",
            placeholder="12345",
        ),
        ConnectionField(
            name="api_token",
            label="API token",
            type=FieldType.SECRET,
            help="A service token with at least Metadata Only and Job Viewer "
            "permissions.",
        ),
        ConnectionField(
            name="project_id",
            label="Project ID",
            type=FieldType.NUMBER,
            required=False,
            help="Leave blank to observe every project in the account.",
        ),
    ),
)


class DbtCloudError(NexusError):
    """dbt Cloud was unreachable, refused the request, or returned nonsense."""


class DbtCloudClient:
    """Read-only client for one dbt Cloud account."""

    def __init__(self, access_url: str, account_id: int, api_token: str, timeout: float = 20.0):
        self._account_id = account_id
        self._client = httpx.Client(
            base_url=f"{access_url.rstrip('/')}/api/v2/accounts/{account_id}",
            headers={
                "Authorization": f"Token {api_token}",
                "Accept": "application/json",
            },
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> DbtCloudClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _get(self, path: str, **params: Any) -> Any:
        try:
            response = self._client.get(path, params=params or None)
        except httpx.HTTPError as exc:
            raise DbtCloudError(f"could not reach dbt Cloud: {exc}") from exc

        if response.status_code in (401, 403):
            raise DbtCloudError(
                "dbt Cloud rejected the token. Check it has Metadata Only and "
                "Job Viewer permissions, and that the Account ID is correct."
            )
        if response.status_code == 404:
            raise DbtCloudError(
                f"dbt Cloud has no resource at {path}. Check the Account ID and "
                "Access URL — regional accounts use a different host."
            )
        if response.status_code >= 400:
            raise DbtCloudError(f"dbt Cloud returned {response.status_code} for {path}")
        return response.json()

    def projects(self) -> list[dict[str, Any]]:
        return self._get("/projects/").get("data") or []

    def jobs(self, project_id: int | None = None) -> list[dict[str, Any]]:
        params = {"project_id": project_id} if project_id else {}
        return self._get("/jobs/", **params).get("data") or []

    def runs(self, job_id: int | None = None, limit: int = 20) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"order_by": "-finished_at", "limit": limit}
        if job_id:
            params["job_definition_id"] = job_id
        return self._get("/runs/", **params).get("data") or []

    def latest_successful_run(self, job_id: int | None = None) -> dict[str, Any] | None:
        """Most recent run that produced artifacts.

        Status 10 is dbt Cloud's 'Success'. Only successful runs are guaranteed to
        have a complete manifest, so a failed run is never used as a graph source.
        """
        for run in self.runs(job_id=job_id, limit=50):
            if run.get("status") == 10:
                return run
        return None

    def manifest(self, run_id: int) -> dict[str, Any]:
        """Fetch manifest.json produced by a run."""
        payload = self._get(f"/runs/{run_id}/artifacts/manifest.json")
        if not isinstance(payload, dict):
            raise DbtCloudError(f"run {run_id} returned a manifest that is not an object")
        return payload


class DbtCloudConnector:
    """Builds the graph from a dbt Cloud project's most recent successful run."""

    system = SYSTEM

    def __init__(self, client: DbtCloudClient, project_id: int | None = None) -> None:
        self._client = client
        self._project_id = project_id

    def collect(self) -> ConnectorResult:
        """Fetch the newest manifest and parse it with the shared manifest reader."""
        run = self._client.latest_successful_run()
        if run is None:
            return ConnectorResult(
                warnings=[
                    "no successful dbt Cloud run found, so there is no manifest to read; "
                    "the graph cannot be built until a job has run successfully"
                ]
            )

        manifest = self._client.manifest(int(run["id"]))

        # The manifest parser reads from disk, which keeps one implementation for
        # both dbt Core and dbt Cloud rather than two that can drift apart.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(json.dumps(manifest))
            result = DbtManifestConnector(path).collect()

        result.warnings.append(
            f"graph built from dbt Cloud run {run['id']} finished at "
            f"{run.get('finished_at', 'unknown time')}"
        )
        return result


def test_connection(config: dict[str, Any]) -> ConnectionTestResult:
    """Probe a dbt Cloud configuration by listing projects and jobs."""
    try:
        client = DbtCloudClient(
            access_url=config.get("access_url") or "https://cloud.getdbt.com",
            account_id=int(config["account_id"]),
            api_token=config["api_token"],
        )
    except (ValueError, KeyError) as exc:
        return ConnectionTestResult.failure(f"invalid configuration: {exc}")

    try:
        projects = client.projects()
        project_id = int(config["project_id"]) if config.get("project_id") else None
        jobs = client.jobs(project_id)
        run = client.latest_successful_run()
    except DbtCloudError as exc:
        return ConnectionTestResult.failure(str(exc))
    except Exception as exc:  # noqa: BLE001
        return ConnectionTestResult.failure(str(exc)[:300])
    finally:
        client.close()

    if not projects:
        return ConnectionTestResult.failure(
            "Connected, but the token can see no projects. Check its permissions."
        )
    if run is None:
        return ConnectionTestResult.failure(
            f"Connected and found {len(projects)} project(s), but no successful run "
            "yet — Nexus needs one to read the manifest."
        )
    return ConnectionTestResult.success(
        f"Connected to dbt Cloud: {len(projects)} project(s), {len(jobs)} job(s)",
        projects=str(len(projects)),
        jobs=str(len(jobs)),
        latest_successful_run=str(run.get("id", "")),
    )
