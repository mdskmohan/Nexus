"""PipelineSpec — the vendor-neutral intermediate representation.

This module is the centre of Nexus. Creation compiles out of a ``PipelineSpec``;
adopting an existing pipeline lifts into one. The diagnosis engine reads it without
caring which direction it came from. See ADR-001.

Two rules govern changes here:

1. A field earns its place only if the compiler or the diagnosis engine reads it.
   Descriptive metadata that nothing acts on belongs in ``tags``.
2. Every field must be expressible on both a declarative SQL target (dbt) and an
   imperative one (Spark). If it cannot be, it is a target-specific detail and
   belongs in ``CompileTarget.options``.
"""

from __future__ import annotations

from datetime import timedelta

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from nexus.errors import SpecValidationError
from nexus.ir.enums import (
    Confidence,
    ConsumerKind,
    Criticality,
    LoadStrategy,
    Materialization,
    Orchestrator,
    SourceKind,
    Warehouse,
)

# IR schema version. Bump on any breaking change to the shape below; lifted and
# persisted specs record the version they were written against.
IR_VERSION = "1.0"

_IDENTIFIER = r"^[a-z][a-z0-9_]*$"


class _Base(BaseModel):
    """Shared configuration for every IR node."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Provenance(_Base):
    """Where a piece of the spec came from and how much we trust it.

    Specs authored by the design agent are uniformly ``DECLARED``. Specs lifted from
    an existing pipeline carry mixed provenance, and the diagnosis engine downgrades
    conclusions that rest on ``INFERRED`` fields.
    """

    confidence: Confidence = Confidence.DECLARED
    recovered_from: str | None = Field(
        default=None,
        description="Artifact the value was read from, e.g. 'dbt/manifest.json#nodes.stg_orders'",
    )


class Column(_Base):
    """A single column in a schema contract."""

    name: str = Field(pattern=_IDENTIFIER)
    data_type: str = Field(description="Warehouse-neutral type name, e.g. 'string', 'int64'")
    nullable: bool = True
    description: str | None = None
    tests: tuple[str, ...] = ()


class SchemaContract(_Base):
    """The shape a dataset promises to its consumers.

    This is the object schema drift is detected against: the compiler emits tests
    from it, and the diagnosis engine diffs observed warehouse schemas against it.
    """

    columns: tuple[Column, ...]
    primary_key: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _primary_key_columns_exist(self) -> SchemaContract:
        names = {c.name for c in self.columns}
        missing = [k for k in self.primary_key if k not in names]
        if missing:
            raise SpecValidationError(
                f"primary_key references unknown columns: {', '.join(sorted(missing))}"
            )
        return self


class FreshnessPolicy(_Base):
    """How stale a source may become before it is a problem.

    Drives both the emitted freshness tests and the ``stale_source`` evidence
    collector, so the same declaration produces prevention and diagnosis.
    """

    warn_after: timedelta
    error_after: timedelta

    @model_validator(mode="after")
    def _error_after_exceeds_warn(self) -> FreshnessPolicy:
        if self.error_after <= self.warn_after:
            raise SpecValidationError("error_after must be greater than warn_after")
        return self


class Source(_Base):
    """An external system a pipeline reads from."""

    id: str = Field(pattern=_IDENTIFIER)
    kind: SourceKind
    connector: str = Field(description="Ingestion mechanism, e.g. 'fivetran', 'airbyte'")
    object_name: str = Field(description="Remote object, e.g. 'salesforce.account'")
    contract: SchemaContract | None = None
    freshness: FreshnessPolicy | None = None
    provenance: Provenance = Provenance()


class Model(_Base):
    """A transformation step producing one dataset.

    ``depends_on`` holds ids of sources or other models. The set of models forms a
    DAG that the compiler topologically sorts and the graph layer mirrors.
    """

    id: str = Field(pattern=_IDENTIFIER)
    sql: str = Field(description="SELECT statement; refs are written as {{ ref('id') }}")
    depends_on: tuple[str, ...] = ()
    materialization: Materialization = Materialization.TABLE
    load_strategy: LoadStrategy = LoadStrategy.FULL_REFRESH
    contract: SchemaContract | None = None
    description: str | None = None
    provenance: Provenance = Provenance()

    @model_validator(mode="after")
    def _incremental_needs_a_key(self) -> Model:
        """MERGE without a primary key silently duplicates rows on re-run."""
        if self.load_strategy is LoadStrategy.MERGE:
            if self.contract is None or not self.contract.primary_key:
                raise SpecValidationError(
                    f"model {self.id!r} uses MERGE but declares no primary key"
                )
        return self


class Consumer(_Base):
    """Something downstream that breaks when the pipeline breaks.

    Recorded so impact analysis can name real business consequences rather than
    counting affected tables.
    """

    id: str = Field(pattern=_IDENTIFIER)
    kind: ConsumerKind
    name: str
    reads: tuple[str, ...] = Field(description="Model ids this consumer depends on")
    owner: str | None = None


class Schedule(_Base):
    """When the pipeline runs and what it promises about completion."""

    cron: str
    timezone: str = "UTC"
    sla: timedelta | None = Field(
        default=None, description="Maximum acceptable time from start to completion"
    )


class Ownership(_Base):
    """Who is accountable. Required — an unowned pipeline cannot be escalated."""

    team: str
    oncall: str | None = None


class CompileTarget(_Base):
    """The customer's chosen stack.

    Nexus does not choose this (ADR-004); the customer does, and we compile onto it.
    """

    warehouse: Warehouse
    orchestrator: Orchestrator
    database: str
    schema_name: str
    options: dict[str, str] = Field(
        default_factory=dict, description="Target-specific escapes that do not belong in the IR"
    )


class PipelineSpec(_Base):
    """A complete, vendor-neutral description of one data product."""

    ir_version: str = IR_VERSION
    id: str = Field(pattern=_IDENTIFIER)
    name: str
    description: str | None = None
    criticality: Criticality = Criticality.MEDIUM
    owner: Ownership
    target: CompileTarget
    schedule: Schedule
    sources: tuple[Source, ...]
    models: tuple[Model, ...]
    consumers: tuple[Consumer, ...] = ()
    tags: tuple[str, ...] = ()

    @field_validator("models")
    @classmethod
    def _at_least_one_model(cls, v: tuple[Model, ...]) -> tuple[Model, ...]:
        if not v:
            raise SpecValidationError("a pipeline must declare at least one model")
        return v

    @model_validator(mode="after")
    def _references_resolve(self) -> PipelineSpec:
        """Every dependency must name a declared source or model, and the graph must be acyclic.

        Checked here rather than at compile time so an invalid spec can never be
        persisted, shown in the UI as valid, or handed to the diagnosis engine.
        """
        known = {s.id for s in self.sources} | {m.id for m in self.models}
        duplicates = len(self.sources) + len(self.models) - len(known)
        if duplicates:
            raise SpecValidationError("source and model ids must be unique across the spec")

        for model in self.models:
            for dep in model.depends_on:
                if dep not in known:
                    raise SpecValidationError(
                        f"model {model.id!r} depends on unknown node {dep!r}"
                    )

        for consumer in self.consumers:
            for ref in consumer.reads:
                if ref not in known:
                    raise SpecValidationError(
                        f"consumer {consumer.id!r} reads unknown node {ref!r}"
                    )

        self._assert_acyclic()
        return self

    def _assert_acyclic(self) -> None:
        """Depth-first cycle detection over the model DAG."""
        edges = {m.id: set(m.depends_on) for m in self.models}
        visiting: set[str] = set()
        done: set[str] = set()

        def visit(node: str) -> None:
            if node in done:
                return
            if node in visiting:
                raise SpecValidationError(f"dependency cycle detected at {node!r}")
            visiting.add(node)
            for dep in edges.get(node, ()):
                visit(dep)
            visiting.discard(node)
            done.add(node)

        for model_id in edges:
            visit(model_id)

    def topological_order(self) -> list[Model]:
        """Return models in dependency order, ready for execution or emission.

        The spec is validated as acyclic on construction, so this cannot loop.
        """
        by_id = {m.id: m for m in self.models}
        ordered: list[Model] = []
        seen: set[str] = set()

        def visit(model_id: str) -> None:
            if model_id in seen or model_id not in by_id:
                return
            seen.add(model_id)
            for dep in by_id[model_id].depends_on:
                visit(dep)
            ordered.append(by_id[model_id])

        for model in self.models:
            visit(model.id)
        return ordered

    def downstream_of(self, node_id: str) -> list[str]:
        """Ids of every model and consumer transitively affected by ``node_id``.

        This is the primitive behind impact analysis: given a failing node, what
        actually breaks.
        """
        affected: set[str] = set()
        frontier = {node_id}
        while frontier:
            current = frontier.pop()
            for model in self.models:
                if current in model.depends_on and model.id not in affected:
                    affected.add(model.id)
                    frontier.add(model.id)
        for consumer in self.consumers:
            if affected.intersection(consumer.reads) or node_id in consumer.reads:
                affected.add(consumer.id)
        return sorted(affected)
