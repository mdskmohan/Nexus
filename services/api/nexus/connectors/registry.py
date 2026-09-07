"""Connector registry.

One place that knows every platform Nexus can connect to, what credentials each
needs, and how to verify a configuration actually works. The API and the UI both
read from here, so adding a platform means adding a spec and a test function —
never touching the form layer or the endpoints.

Driver imports are deliberately deferred into the test functions. A deployment
that never touches Snowflake should not need its driver installed, and importing
every driver at module load would make that impossible.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Any

from nexus.connectors import dbt as dbt_core
from nexus.connectors.dbt_cloud import connector as dbt_cloud
from nexus.connectors.github import connector as github
from nexus.connectors.spec import ConnectionTestResult, ConnectorSpec
from nexus.connectors.warehouse import bigquery, databricks, postgres, snowflake
from nexus.connectors.airflow import connector as airflow
from nexus.errors import NexusError

TestFn = Callable[[dict[str, Any]], ConnectionTestResult]

#: Hard ceiling on any connection probe. Drivers vary wildly in how they handle an
#: unreachable host — some retry for minutes — and a configuration form that never
#: returns is worse than one that reports a timeout.
PROBE_TIMEOUT_SECONDS = 30.0


class UnknownConnector(NexusError):
    """A configuration named a platform that does not exist."""


_MODULES = (
    dbt_core.manifest,
    dbt_cloud,
    airflow,
    postgres,
    snowflake,
    databricks,
    bigquery,
    github,
)

#: platform id -> (spec, test function)
_REGISTRY: dict[str, tuple[ConnectorSpec, TestFn]] = {
    module.SPEC.id: (module.SPEC, module.test_connection) for module in _MODULES
}


def all_specs() -> list[ConnectorSpec]:
    """Every supported platform, ordered by category then name for stable display."""
    return sorted(
        (spec for spec, _ in _REGISTRY.values()),
        key=lambda s: (s.category.value, s.name),
    )


def get_spec(connector_id: str) -> ConnectorSpec:
    """The spec for one platform."""
    entry = _REGISTRY.get(connector_id)
    if entry is None:
        known = ", ".join(sorted(_REGISTRY))
        raise UnknownConnector(f"no connector {connector_id!r}; known: {known}")
    return entry[0]


def driver_available(spec: ConnectorSpec) -> bool:
    """Whether this platform's driver is importable in the running environment.

    Surfaced in the UI so a failed connection reads as "the driver is missing"
    rather than as a credential problem.
    """
    if not spec.driver_package:
        return True
    import importlib.util

    # Distribution names do not always match module names.
    module = {
        "psycopg[binary]": "psycopg",
        "snowflake-connector-python": "snowflake.connector",
        "databricks-sql-connector": "databricks.sql",
        "google-cloud-bigquery": "google.cloud.bigquery",
    }.get(spec.driver_package, spec.driver_package.replace("-", "_"))

    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def test_connection(connector_id: str, config: dict[str, Any]) -> ConnectionTestResult:
    """Validate a configuration, then probe the platform with it.

    Validation runs first so a missing field is reported as a form error rather
    than as an obscure driver exception.
    """
    spec, probe = _REGISTRY.get(connector_id, (None, None))
    if spec is None or probe is None:
        raise UnknownConnector(f"no connector {connector_id!r}")

    if problems := spec.validate(config):
        return ConnectionTestResult.failure("; ".join(problems))

    if not driver_available(spec):
        return ConnectionTestResult.failure(
            f"The {spec.name} driver is not installed on the server. "
            f"Install the '{spec.driver_package}' package and retry."
        )

    # Run the probe under a deadline. The worker thread may outlive the deadline —
    # a blocked driver call cannot be interrupted — but the caller always gets an
    # answer, which is what the form needs.
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(probe, config)
        try:
            return future.result(timeout=PROBE_TIMEOUT_SECONDS)
        except FutureTimeout:
            pool.shutdown(wait=False, cancel_futures=True)
            return ConnectionTestResult.failure(
                f"{spec.name} did not respond within "
                f"{int(PROBE_TIMEOUT_SECONDS)}s. Check the host is reachable from "
                "this network and that any firewall allows it."
            )
        except Exception as exc:  # noqa: BLE001 - a driver must never crash the API
            return ConnectionTestResult.failure(
                f"{spec.name} connection failed: "
                f"{str(exc).strip().splitlines()[0][:280]}"
            )
