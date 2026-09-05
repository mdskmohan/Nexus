"""Tests for the dbt manifest connector.

These run against a real manifest produced by `dbt parse` rather than a
handwritten one, so they catch the shapes dbt actually emits — including the
ones that differ from the documentation.
"""

import json
from pathlib import Path

import pytest

from nexus.connectors.dbt import DbtManifestConnector, ManifestError
from nexus.graph.entities import EdgeKind, NodeKind

FIXTURE = Path(__file__).parent / "fixtures" / "dbt" / "manifest_v12.json"


@pytest.fixture
def result():
    return DbtManifestConnector(FIXTURE).collect()


def _by_kind(result, kind):
    return {n.name: n for n in result.nodes if n.kind is kind}


class TestNodeRecovery:
    def test_models_are_recovered(self, result) -> None:
        models = _by_kind(result, NodeKind.MODEL)
        assert set(models) == {"stg_accounts", "stg_users", "dim_customer"}

    def test_sources_are_recovered(self, result) -> None:
        sources = _by_kind(result, NodeKind.SOURCE)
        assert set(sources) == {"salesforce.account", "app.users"}

    def test_tests_are_recovered(self, result) -> None:
        tests = _by_kind(result, NodeKind.TEST)
        assert len(tests) == 4

    def test_exposure_becomes_a_consumer(self, result) -> None:
        """Impact analysis has to reach past the warehouse to something a human notices."""
        consumers = _by_kind(result, NodeKind.CONSUMER)
        assert "Executive Overview" in consumers
        assert consumers["Executive Overview"].attributes["exposure_type"] == "dashboard"

    def test_node_ids_are_namespaced(self, result) -> None:
        assert all(n.id.startswith("dbt:") for n in result.nodes)


class TestAttributes:
    def test_materialization_is_read_from_config(self, result) -> None:
        models = _by_kind(result, NodeKind.MODEL)
        assert models["dim_customer"].attributes["materialized"] == "table"
        assert models["stg_accounts"].attributes["materialized"] == "view"

    def test_raw_sql_is_captured(self, result) -> None:
        """The diagnosis engine needs the authored SQL to explain a join failure."""
        models = _by_kind(result, NodeKind.MODEL)
        assert "LEFT JOIN" in models["dim_customer"].attributes["raw_code"]

    def test_owner_is_read_from_meta(self, result) -> None:
        models = _by_kind(result, NodeKind.MODEL)
        assert models["dim_customer"].attributes["owner"] == "data-platform"

    def test_declared_freshness_is_converted_to_seconds(self, result) -> None:
        sources = _by_kind(result, NodeKind.SOURCE)
        account = sources["salesforce.account"]
        assert account.attributes["freshness_warn_seconds"] == str(6 * 3600)
        assert account.attributes["freshness_error_seconds"] == str(24 * 3600)

    def test_undeclared_freshness_is_omitted(self, result) -> None:
        """dbt emits a freshness object with null count/period even when undeclared.

        Treating that as a real policy would invent thresholds nobody set, so the
        null shape must produce no freshness attributes at all.
        """
        sources = _by_kind(result, NodeKind.SOURCE)
        users = sources["app.users"]
        assert "freshness_warn_seconds" not in users.attributes
        assert "freshness_error_seconds" not in users.attributes


class TestEdges:
    def test_model_lineage_is_recovered(self, result) -> None:
        deps = {
            (e.source, e.target)
            for e in result.edges
            if e.kind is EdgeKind.DEPENDS_ON
        }
        assert ("dbt:model.shop.stg_accounts", "dbt:model.shop.dim_customer") in deps
        assert ("dbt:model.shop.stg_users", "dbt:model.shop.dim_customer") in deps
        assert ("dbt:source.shop.salesforce.account", "dbt:model.shop.stg_accounts") in deps

    def test_tests_point_at_what_they_assert_on(self, result) -> None:
        """A failing test must resolve to the node whose contract it guards."""
        tested = {e.target for e in result.edges if e.kind is EdgeKind.TESTS}
        assert all(t.startswith("dbt:test.") for t in tested)
        guarded = {e.source for e in result.edges if e.kind is EdgeKind.TESTS}
        assert "dbt:model.shop.dim_customer" in guarded

    def test_exposure_reads_its_model(self, result) -> None:
        reads = {(e.source, e.target) for e in result.edges if e.kind is EdgeKind.READS}
        assert (
            "dbt:model.shop.dim_customer",
            "dbt:exposure.shop.exec_dashboard",
        ) in reads

    def test_no_dangling_edges_in_a_complete_manifest(self, result) -> None:
        assert result.warnings == []


class TestFailureModes:
    def test_missing_manifest_is_reported_clearly(self, tmp_path: Path) -> None:
        with pytest.raises(ManifestError, match="no manifest at"):
            DbtManifestConnector(tmp_path / "absent.json").collect()

    def test_invalid_json_is_reported_clearly(self, tmp_path: Path) -> None:
        bad = tmp_path / "manifest.json"
        bad.write_text("{not json")
        with pytest.raises(ManifestError, match="not valid JSON"):
            DbtManifestConnector(bad).collect()

    def test_old_schema_version_is_refused(self, tmp_path: Path) -> None:
        """Below v7 the node shape differs enough that misparsing is a real risk."""
        old = tmp_path / "manifest.json"
        old.write_text(
            json.dumps(
                {"metadata": {"dbt_schema_version": "https://x/dbt/manifest/v4.json"}}
            )
        )
        with pytest.raises(ManifestError, match="older than the supported minimum"):
            DbtManifestConnector(old).collect()

    def test_unknown_fields_are_tolerated(self, tmp_path: Path) -> None:
        """dbt adds keys in minor releases; a hard failure would break on upgrade."""
        payload = json.loads(FIXTURE.read_text())
        payload["a_key_from_the_future"] = {"anything": True}
        payload["nodes"]["model.shop.dim_customer"]["brand_new_field"] = 42
        path = tmp_path / "manifest.json"
        path.write_text(json.dumps(payload))
        assert len(DbtManifestConnector(path).collect().nodes) == 10

    def test_dangling_edge_is_warned_not_dropped(self, tmp_path: Path) -> None:
        """A silent gap in the graph becomes a diagnosis that cannot explain itself."""
        payload = json.loads(FIXTURE.read_text())
        payload["nodes"]["model.shop.dim_customer"]["depends_on"]["nodes"].append(
            "model.shop.deleted_upstream"
        )
        path = tmp_path / "manifest.json"
        path.write_text(json.dumps(payload))
        warnings = DbtManifestConnector(path).collect().warnings
        assert any("deleted_upstream" in w for w in warnings)
