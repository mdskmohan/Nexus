"""Integration tests for the Postgres warehouse connector.

These run against the real Postgres in the local stack — real DDL, real
information_schema, real drift. They skip when the stack is down.
"""

from __future__ import annotations

import time

import pytest

from nexus.connectors.warehouse.postgres import PostgresConnector
from nexus.connectors.warehouse.schema import ChangeKind, diff_snapshots, normalise_type
from tests.conftest_stack import POSTGRES_DSN, SKIP_REASON, postgres_available

pytestmark = pytest.mark.skipif(not postgres_available(), reason=SKIP_REASON)


@pytest.fixture
def connection():
    import psycopg

    conn = psycopg.connect(POSTGRES_DSN, autocommit=True)
    yield conn
    conn.close()


@pytest.fixture
def connector(connection):
    return PostgresConnector(connection)


class TestSnapshot:
    def test_reads_real_user_tables(self, connector) -> None:
        keys = {t.key for t in connector.snapshot().tables}
        assert "analytics.raw.salesforce_account" in keys
        assert "analytics.raw.app_users" in keys

    def test_system_schemas_are_excluded(self, connector) -> None:
        """information_schema and pg_catalog describe the server, not the data."""
        schemas = {t.schema for t in connector.snapshot().tables}
        assert not schemas & {"pg_catalog", "information_schema", "pg_toast"}

    def test_types_are_normalised_from_real_postgres_names(self, connector) -> None:
        table = next(
            t for t in connector.snapshot().tables if t.name == "salesforce_account"
        )
        cols = table.column_map()
        assert cols["id"].data_type == "integer"
        # Postgres reports 'text'; the shared vocabulary calls it 'string'.
        assert cols["name"].data_type == "string"
        assert cols["name"].raw_type == "text"
        assert cols["_loaded_at"].data_type == "timestamp"
        assert cols["_loaded_at"].raw_type == "timestamp without time zone"

    def test_nullability_is_read_correctly(self, connector) -> None:
        table = next(
            t for t in connector.snapshot().tables if t.name == "salesforce_account"
        )
        cols = table.column_map()
        assert cols["id"].nullable is False
        assert cols["_loaded_at"].nullable is False

    def test_snapshot_of_unchanged_database_is_stable(self, connector) -> None:
        """Two captures with no DDL between them must produce no drift."""
        first = connector.snapshot()
        time.sleep(0.05)
        second = connector.snapshot()
        assert diff_snapshots(first, second) == []


class TestRealDrift:
    """Alters the live schema, then restores it."""

    def test_type_change_is_detected(self, connector, connection) -> None:
        """The reference incident: an upstream id migrating from integer to string."""
        before = connector.snapshot()
        time.sleep(0.01)
        with connection.cursor() as cur:
            cur.execute(
                "ALTER TABLE raw.salesforce_account "
                "ALTER COLUMN id TYPE varchar(18) USING id::varchar"
            )
        try:
            changes = diff_snapshots(before, connector.snapshot())
            drift = [c for c in changes if c.kind is ChangeKind.TYPE_CHANGED]
            assert len(drift) == 1
            assert drift[0].column == "id"
            assert drift[0].before == "integer"
            assert drift[0].after == "string"
            assert drift[0].is_breaking
            assert (
                drift[0].describe()
                == "analytics.raw.salesforce_account.id changed from integer to string"
            )
            # The window is what makes the claim citable.
            assert drift[0].observed_before < drift[0].observed_after
        finally:
            with connection.cursor() as cur:
                cur.execute(
                    "ALTER TABLE raw.salesforce_account "
                    "ALTER COLUMN id TYPE integer USING id::integer"
                )

    def test_dropped_column_is_detected(self, connector, connection) -> None:
        before = connector.snapshot()
        time.sleep(0.01)
        with connection.cursor() as cur:
            cur.execute("ALTER TABLE raw.app_users DROP COLUMN email")
        try:
            changes = diff_snapshots(before, connector.snapshot())
            dropped = [c for c in changes if c.kind is ChangeKind.COLUMN_REMOVED]
            assert [c.column for c in dropped] == ["email"]
            assert dropped[0].is_breaking
        finally:
            with connection.cursor() as cur:
                cur.execute("ALTER TABLE raw.app_users ADD COLUMN email text")

    def test_added_column_is_not_breaking(self, connector, connection) -> None:
        """Additive changes are reported but must not be raised as candidate causes."""
        before = connector.snapshot()
        time.sleep(0.01)
        with connection.cursor() as cur:
            cur.execute("ALTER TABLE raw.app_users ADD COLUMN signup_source text")
        try:
            added = [
                c
                for c in diff_snapshots(before, connector.snapshot())
                if c.kind is ChangeKind.COLUMN_ADDED
            ]
            assert [c.column for c in added] == ["signup_source"]
            assert not added[0].is_breaking
        finally:
            with connection.cursor() as cur:
                cur.execute("ALTER TABLE raw.app_users DROP COLUMN signup_source")

    def test_new_table_is_detected(self, connector, connection) -> None:
        before = connector.snapshot()
        time.sleep(0.01)
        with connection.cursor() as cur:
            cur.execute("CREATE TABLE raw.tmp_probe (id integer)")
        try:
            added = [
                c
                for c in diff_snapshots(before, connector.snapshot())
                if c.kind is ChangeKind.TABLE_ADDED
            ]
            assert [c.table for c in added] == ["analytics.raw.tmp_probe"]
        finally:
            with connection.cursor() as cur:
                cur.execute("DROP TABLE raw.tmp_probe")


class TestGraphEntities:
    def test_emits_a_node_per_table(self, connector) -> None:
        result = connector.collect()
        names = {n.name for n in result.nodes}
        assert "raw.salesforce_account" in names
        assert all(n.id.startswith("postgres:") for n in result.nodes)


class TestTypeNormalisation:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("integer", "integer"),
            ("bigint", "integer"),
            ("text", "string"),
            ("character varying", "string"),
            ("varchar(18)", "string"),
            ("NUMBER(38,0)", "numeric"),
            ("timestamp without time zone", "timestamp"),
            ("timestamp with time zone", "timestamptz"),
            ("jsonb", "json"),
        ],
    )
    def test_known_types_collapse(self, raw: str, expected: str) -> None:
        assert normalise_type(raw) == expected

    def test_precision_is_discarded(self) -> None:
        """NUMBER(18,0) widening to NUMBER(38,0) is not drift a consumer can see."""
        assert normalise_type("NUMBER(18,0)") == normalise_type("NUMBER(38,0)")

    def test_unknown_type_passes_through(self) -> None:
        assert normalise_type("SomeCustomType") == "somecustomtype"
