"""Shared helpers for tests that run against the real local stack.

Tests using these skip cleanly when the stack is not running, so the suite still
passes on a machine without Docker. They are not mocked: when they run, they run
against real Postgres and real Airflow.

    docker compose -f stack/docker-compose.yml up -d
"""

from __future__ import annotations

import os

POSTGRES_DSN = os.environ.get(
    "NEXUS_TEST_POSTGRES_DSN", "postgresql://nexus:nexus@localhost:55432/analytics"
)
AIRFLOW_URL = os.environ.get("NEXUS_TEST_AIRFLOW_URL", "http://localhost:18080")
AIRFLOW_AUTH = ("nexus", "nexus")

SKIP_REASON = (
    "local stack not running — start it with "
    "`docker compose -f stack/docker-compose.yml up -d`"
)


def postgres_available() -> bool:
    """Whether the stack's Postgres is reachable."""
    try:
        import psycopg

        with psycopg.connect(POSTGRES_DSN, connect_timeout=2):
            return True
    except Exception:
        return False


def airflow_available() -> bool:
    """Whether the stack's Airflow REST API is reachable and healthy."""
    try:
        import urllib.request

        with urllib.request.urlopen(f"{AIRFLOW_URL}/health", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False
