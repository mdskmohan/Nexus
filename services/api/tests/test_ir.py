"""Tests for the PipelineSpec IR.

The validators here are the last line of defence before a spec reaches the compiler
or the diagnosis engine, so each one gets an explicit negative test.
"""

from datetime import timedelta

import pytest

from nexus.errors import SpecValidationError
from nexus.ir.enums import LoadStrategy, Materialization
from nexus.ir.spec import (
    Column,
    FreshnessPolicy,
    Model,
    PipelineSpec,
    SchemaContract,
)


class TestValidation:
    def test_reference_graph_resolves(self, customer_360: PipelineSpec) -> None:
        assert customer_360.id == "customer_360"
        assert len(customer_360.models) == 3

    def test_unknown_dependency_is_rejected(self, customer_360: PipelineSpec) -> None:
        broken = customer_360.model_dump()
        broken["models"][0]["depends_on"] = ("does_not_exist",)
        with pytest.raises(SpecValidationError, match="unknown node"):
            PipelineSpec(**broken)

    def test_cycle_is_rejected(self, customer_360: PipelineSpec) -> None:
        broken = customer_360.model_dump()
        # stg_accounts <- dim_customer, and dim_customer already depends on stg_accounts
        broken["models"][0]["depends_on"] = ("dim_customer",)
        with pytest.raises(SpecValidationError, match="cycle"):
            PipelineSpec(**broken)

    def test_duplicate_ids_are_rejected(self, customer_360: PipelineSpec) -> None:
        broken = customer_360.model_dump()
        broken["models"][1]["id"] = "stg_accounts"
        with pytest.raises(SpecValidationError, match="unique"):
            PipelineSpec(**broken)

    def test_consumer_reading_unknown_node_is_rejected(
        self, customer_360: PipelineSpec
    ) -> None:
        broken = customer_360.model_dump()
        broken["consumers"][0]["reads"] = ("ghost_table",)
        with pytest.raises(SpecValidationError, match="reads unknown node"):
            PipelineSpec(**broken)

    def test_empty_pipeline_is_rejected(self, customer_360: PipelineSpec) -> None:
        broken = customer_360.model_dump()
        broken["models"] = []
        with pytest.raises(SpecValidationError, match="at least one model"):
            PipelineSpec(**broken)

    def test_merge_without_primary_key_is_rejected(self) -> None:
        """MERGE with no key silently duplicates rows — the most expensive class of bug."""
        with pytest.raises(SpecValidationError, match="no primary key"):
            Model(
                id="bad_merge",
                sql="SELECT 1",
                materialization=Materialization.INCREMENTAL,
                load_strategy=LoadStrategy.MERGE,
            )

    def test_primary_key_must_reference_declared_columns(self) -> None:
        with pytest.raises(SpecValidationError, match="unknown columns"):
            SchemaContract(
                columns=(Column(name="a", data_type="string"),),
                primary_key=("b",),
            )

    def test_freshness_thresholds_must_be_ordered(self) -> None:
        with pytest.raises(SpecValidationError, match="greater than"):
            FreshnessPolicy(warn_after=timedelta(hours=6), error_after=timedelta(hours=1))

    def test_identifiers_must_be_snake_case(self, customer_360: PipelineSpec) -> None:
        broken = customer_360.model_dump()
        broken["models"][0]["id"] = "StgAccounts"
        with pytest.raises(Exception):
            PipelineSpec(**broken)


class TestTraversal:
    def test_topological_order_places_dependencies_first(
        self, customer_360: PipelineSpec
    ) -> None:
        order = [m.id for m in customer_360.topological_order()]
        assert order.index("stg_accounts") < order.index("dim_customer")
        assert order.index("stg_users") < order.index("dim_customer")

    def test_downstream_of_source_reaches_consumer(
        self, customer_360: PipelineSpec
    ) -> None:
        """Impact analysis: a broken source must surface the dashboard, not just tables."""
        affected = customer_360.downstream_of("salesforce_account")
        assert affected == ["dim_customer", "exec_dashboard", "stg_accounts"]

    def test_downstream_of_leaf_is_only_its_consumers(
        self, customer_360: PipelineSpec
    ) -> None:
        assert customer_360.downstream_of("dim_customer") == ["exec_dashboard"]

    def test_downstream_traversal_is_transitive(
        self, customer_360: PipelineSpec
    ) -> None:
        """A second-hop source must still reach the dashboard three edges away."""
        assert customer_360.downstream_of("app_users") == [
            "dim_customer",
            "exec_dashboard",
            "stg_users",
        ]


class TestImmutability:
    def test_spec_is_frozen(self, customer_360: PipelineSpec) -> None:
        """Specs are versioned artifacts, never mutated in place."""
        with pytest.raises(Exception):
            customer_360.name = "changed"  # type: ignore[misc]

    def test_unknown_fields_are_rejected(self, customer_360: PipelineSpec) -> None:
        payload = customer_360.model_dump()
        payload["surprise"] = True
        with pytest.raises(Exception):
            PipelineSpec(**payload)
