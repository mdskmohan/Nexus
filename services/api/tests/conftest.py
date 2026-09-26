"""Tests run against a real Postgres: a separate `nexus_test` database on the
dev server (make up), migrated from scratch at the start of each session."""

import os

os.environ.setdefault("NEXUS_DATABASE_URL", "postgresql+psycopg://nexus_app:nexus_app_dev@localhost:5544/nexus_test")
os.environ.setdefault("NEXUS_DATABASE_OWNER_URL", "postgresql+psycopg://nexus_owner:nexus_owner_dev@localhost:5544/nexus_test")
os.environ.setdefault("NEXUS_JWT_SECRET", "test-secret-test-secret-test-secret")

import tempfile  # noqa: E402

os.environ.setdefault("NEXUS_STORAGE_DIR", tempfile.mkdtemp(prefix="nexus-test-storage-"))
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

API_DIR = Path(__file__).resolve().parents[1]
TENANT_TABLES = "audit_events, artifacts, run_steps, runs, playbooks, passages, documents, matters, users, firms, jobs"


def _owner_url(db: str) -> str:
    return os.environ["NEXUS_DATABASE_OWNER_URL"].rsplit("/", 1)[0] + f"/{db}"


@pytest.fixture(scope="session", autouse=True)
def database():
    admin = create_engine(_owner_url("nexus"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS nexus_test WITH (FORCE)"))
        conn.execute(text("CREATE DATABASE nexus_test"))
    admin.dispose()
    with create_engine(_owner_url("nexus_test"), isolation_level="AUTOCOMMIT").connect() as conn:
        conn.execute(text("GRANT CONNECT ON DATABASE nexus_test TO nexus_app"))
        conn.execute(text("GRANT USAGE ON SCHEMA public TO nexus_app"))
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "migrations"))
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def clean():
    """Empty every table between tests. Runs as the owner; the audit trigger is
    disabled only for this cleanup."""
    yield
    engine = create_engine(os.environ["NEXUS_DATABASE_OWNER_URL"])
    with engine.begin() as conn:
        conn.execute(text("SET session_replication_role = replica"))
        conn.execute(text(f"TRUNCATE {TENANT_TABLES} CASCADE"))
    engine.dispose()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from nexus.main import app

    return TestClient(app, headers={"x-nexus-client": "test"})


def signup(client, firm="Madiraju & Co", email="partner@madiraju.example", password="correct horse battery"):
    r = client.post("/api/auth/signup", json={"firm_name": firm, "name": "Test Admin",
                                               "email": email, "password": password})
    assert r.status_code == 201, r.text
    return r
