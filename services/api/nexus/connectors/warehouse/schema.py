"""Warehouse schema snapshots and drift detection.

The evidence source behind the most common class of pipeline failure: an upstream
column changed type or vanished, and a downstream join broke hours later.
Reconstructing that from logs after the fact is guesswork; comparing two
snapshots is arithmetic.

Snapshots are captured on a schedule and retained, so a drift is always
expressible as a pair of timestamped observations. That is what makes a
diagnosis citable rather than merely plausible.

Postgres and Snowflake both expose ``INFORMATION_SCHEMA.COLUMNS`` with the same
essential shape, so the model here is shared; only the query dialect and type
vocabulary differ per warehouse.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ChangeKind(StrEnum):
    """A single observed difference between two snapshots."""

    TABLE_ADDED = "table_added"
    TABLE_REMOVED = "table_removed"
    COLUMN_ADDED = "column_added"
    COLUMN_REMOVED = "column_removed"
    TYPE_CHANGED = "type_changed"
    NULLABILITY_CHANGED = "nullability_changed"


#: Changes that can break a consumer with no code change on our side. Used to
#: decide whether a drift is worth raising as a candidate root cause.
BREAKING_CHANGES = frozenset(
    {
        ChangeKind.TABLE_REMOVED,
        ChangeKind.COLUMN_REMOVED,
        ChangeKind.TYPE_CHANGED,
        ChangeKind.NULLABILITY_CHANGED,
    }
)


@dataclass(frozen=True, slots=True)
class Column:
    """One column as the warehouse reports it."""

    name: str
    #: Normalised type name (see ``normalise_type``), not the raw warehouse string.
    data_type: str
    nullable: bool
    #: The raw type exactly as reported, retained so evidence can quote the warehouse.
    raw_type: str = ""


@dataclass(frozen=True, slots=True)
class Table:
    """One table's column set at a point in time."""

    database: str
    schema: str
    name: str
    columns: tuple[Column, ...]

    @property
    def key(self) -> str:
        """Fully-qualified, case-normalised identity used to match across snapshots."""
        return f"{self.database}.{self.schema}.{self.name}".lower()

    def column_map(self) -> dict[str, Column]:
        return {c.name.lower(): c for c in self.columns}


@dataclass(frozen=True, slots=True)
class SchemaSnapshot:
    """Every table observed in one warehouse at one moment."""

    captured_at: datetime
    tables: tuple[Table, ...] = ()
    #: Which warehouse produced this, e.g. "postgres". Carried into evidence.
    system: str = ""

    def table_map(self) -> dict[str, Table]:
        return {t.key: t for t in self.tables}


@dataclass(frozen=True, slots=True)
class SchemaChange:
    """One difference between two snapshots, with everything needed to cite it."""

    kind: ChangeKind
    table: str
    column: str | None
    before: str | None
    after: str | None
    observed_before: datetime
    observed_after: datetime
    system: str = ""

    @property
    def is_breaking(self) -> bool:
        """Whether this can break a consumer with no change on our side."""
        return self.kind in BREAKING_CHANGES

    def describe(self) -> str:
        """A one-line summary suitable for display as evidence."""
        match self.kind:
            case ChangeKind.TYPE_CHANGED:
                return f"{self.table}.{self.column} changed from {self.before} to {self.after}"
            case ChangeKind.NULLABILITY_CHANGED:
                became = "nullable" if self.after == "nullable" else "not null"
                return f"{self.table}.{self.column} became {became}"
            case ChangeKind.COLUMN_REMOVED:
                return f"{self.table}.{self.column} was removed"
            case ChangeKind.COLUMN_ADDED:
                return f"{self.table}.{self.column} was added"
            case ChangeKind.TABLE_REMOVED:
                return f"{self.table} was removed"
            case _:
                return f"{self.table} was added"


#: Warehouse type names collapsed to a small shared vocabulary. Comparing raw type
#: strings across warehouses invents drift — Snowflake reports NUMBER where
#: Postgres reports integer for the same logical column.
_TYPE_ALIASES = {
    "int": "integer", "int2": "integer", "int4": "integer", "int8": "integer",
    "integer": "integer", "bigint": "integer", "smallint": "integer",
    "tinyint": "integer", "byteint": "integer",
    "number": "numeric", "numeric": "numeric", "decimal": "numeric",
    "float": "float", "float4": "float", "float8": "float",
    "double": "float", "double precision": "float", "real": "float",
    "varchar": "string", "character varying": "string", "char": "string",
    "character": "string", "text": "string", "string": "string",
    "date": "date",
    "timestamp": "timestamp", "timestamp_ntz": "timestamp",
    "timestamp without time zone": "timestamp",
    "timestamp_tz": "timestamptz", "timestamp_ltz": "timestamptz",
    "timestamp with time zone": "timestamptz", "timestamptz": "timestamptz",
    "boolean": "boolean", "bool": "boolean",
    "variant": "variant", "object": "object", "array": "array",
    "json": "json", "jsonb": "json",
}


def normalise_type(raw: str) -> str:
    """Collapse a warehouse type name to the shared vocabulary.

    Precision and scale are deliberately discarded: NUMBER(18,0) widening to
    NUMBER(38,0) is not a change a consumer can observe, and reporting it would
    bury the drifts that matter. A move *between* families — integer to string —
    is what breaks joins.
    """
    cleaned = raw.strip().lower()
    if "(" in cleaned:
        cleaned = cleaned.split("(", 1)[0].strip()
    return _TYPE_ALIASES.get(cleaned, cleaned)


def diff_snapshots(before: SchemaSnapshot, after: SchemaSnapshot) -> list[SchemaChange]:
    """Every difference between two snapshots, ordered by table then column.

    Both directions are reported: a dropped table matters for diagnosis, an added
    one matters for keeping the graph honest.
    """
    if after.captured_at < before.captured_at:
        raise ValueError("'after' snapshot predates 'before'; arguments are reversed")

    changes: list[SchemaChange] = []
    before_tables = before.table_map()
    after_tables = after.table_map()
    system = after.system or before.system

    def change(kind: ChangeKind, table: str, **kw: str | None) -> SchemaChange:
        return SchemaChange(
            kind=kind,
            table=table,
            column=kw.get("column"),
            before=kw.get("before"),
            after=kw.get("after"),
            observed_before=before.captured_at,
            observed_after=after.captured_at,
            system=system,
        )

    for key in sorted(set(before_tables) | set(after_tables)):
        old, new = before_tables.get(key), after_tables.get(key)

        if old is None:
            changes.append(change(ChangeKind.TABLE_ADDED, key))
            continue
        if new is None:
            changes.append(change(ChangeKind.TABLE_REMOVED, key))
            continue

        old_cols, new_cols = old.column_map(), new.column_map()
        for col in sorted(set(old_cols) | set(new_cols)):
            old_col, new_col = old_cols.get(col), new_cols.get(col)

            if old_col is None:
                changes.append(change(ChangeKind.COLUMN_ADDED, key, column=col))
                continue
            if new_col is None:
                changes.append(change(ChangeKind.COLUMN_REMOVED, key, column=col))
                continue

            if old_col.data_type != new_col.data_type:
                changes.append(
                    change(
                        ChangeKind.TYPE_CHANGED, key, column=col,
                        before=old_col.data_type, after=new_col.data_type,
                    )
                )
            if old_col.nullable != new_col.nullable:
                changes.append(
                    change(
                        ChangeKind.NULLABILITY_CHANGED, key, column=col,
                        before="nullable" if old_col.nullable else "not null",
                        after="nullable" if new_col.nullable else "not null",
                    )
                )

    return changes
