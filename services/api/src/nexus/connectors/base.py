"""What every warehouse connector does, and the metadata it returns.

Connectors only ever read. They return the tables and columns the
connection's role can see, any declared foreign keys, and small samples of
distinct values (used to check whether a suggested join really matches).
Every query is built here or in the connector, never from user text.
"""

import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlglot import exp

from nexus.connectors.spec import Spec, TestResult


@dataclass(frozen=True, slots=True)
class ColumnMeta:
    name: str
    data_type: str      # normalised family, see normalise_type
    raw_type: str
    nullable: bool
    ordinal: int
    comment: str = ""


@dataclass(frozen=True, slots=True)
class TableMeta:
    database: str
    schema: str
    name: str
    kind: str           # 'table' | 'view'
    columns: tuple[ColumnMeta, ...]
    comment: str = ""

    @property
    def key(self) -> str:
        return f"{self.database}.{self.schema}.{self.name}".lower()


@dataclass(frozen=True, slots=True)
class ForeignKey:
    table: str          # TableMeta.key
    column: str
    ref_table: str
    ref_column: str
    name: str = ""


class ConnectorError(RuntimeError):
    """A connector failed; the message is safe to show (it never contains credentials)."""


def clean(exc: Exception) -> str:
    """A driver error's first line, without anything from the configuration."""
    text = str(exc).strip()
    return (text.splitlines()[0] if text else exc.__class__.__name__)[:300]


def _patterns(value: str | None) -> list[re.Pattern]:
    out = []
    for part in (value or "").split(","):
        part = part.strip()
        if part:
            try:
                out.append(re.compile(part, re.IGNORECASE))
            except re.error as exc:
                raise ConnectorError(f"The schema filter {part!r} is not a valid pattern: {exc}") from exc
    return out


def schema_allowed(settings: dict, schema: str) -> bool:
    """Apply a connection's schema filters (comma-separated regular expressions,
    matched anywhere in the name, as OpenMetadata's filter patterns are)."""
    include, exclude = _patterns(settings.get("schemas_include")), _patterns(settings.get("schemas_exclude"))
    if include and not any(p.search(schema) for p in include):
        return False
    return not any(p.search(schema) for p in exclude)


# Warehouse type names collapsed to a small shared vocabulary, so a column can be
# compared across warehouses (Snowflake's NUMBER and Postgres's integer).
_TYPE_ALIASES = {
    "int": "integer", "int2": "integer", "int4": "integer", "int8": "integer", "integer": "integer",
    "bigint": "integer", "smallint": "integer", "tinyint": "integer", "byteint": "integer", "long": "integer",
    "short": "integer", "byte": "integer",
    "number": "numeric", "numeric": "numeric", "decimal": "numeric",
    "float": "float", "float4": "float", "float8": "float", "double": "float", "double precision": "float",
    "real": "float",
    "varchar": "string", "character varying": "string", "char": "string", "character": "string",
    "text": "string", "string": "string", "uuid": "string",
    "date": "date",
    "timestamp": "timestamp", "timestamp_ntz": "timestamp", "timestamp without time zone": "timestamp",
    "timestamp_tz": "timestamptz", "timestamp_ltz": "timestamptz", "timestamp with time zone": "timestamptz",
    "timestamptz": "timestamptz",
    "boolean": "boolean", "bool": "boolean",
    "variant": "json", "object": "json", "json": "json", "jsonb": "json", "array": "array",
}


def normalise_type(raw: str) -> str:
    cleaned = raw.strip().lower()
    if "(" in cleaned:
        cleaned = cleaned.split("(", 1)[0].strip()
    if "<" in cleaned:
        cleaned = cleaned.split("<", 1)[0].strip()
    return _TYPE_ALIASES.get(cleaned, cleaned)


class Warehouse(ABC):
    """One open connection to a warehouse. Use as a context manager."""

    spec: Spec
    dialect: str  # sqlglot dialect name

    def __init__(self, settings: dict, secrets: dict):
        self.settings = settings
        self.secrets = secrets
        self._conn: Any = None
        # Called as (schema, schemas done, schemas in total, tables in that schema) by connectors that
        # read schema by schema, so a run can report progress. Connectors reading the whole catalogue
        # in one query never call it.
        self.on_schema: Callable[[str, int, int, int], None] | None = None

    @abstractmethod
    def _connect(self) -> Any: ...

    @abstractmethod
    def tables(self) -> list[TableMeta]: ...

    @abstractmethod
    def test(self) -> TestResult: ...

    def foreign_keys(self) -> list[ForeignKey]:
        return []

    def __enter__(self) -> "Warehouse":
        try:
            self._conn = self._connect()
        except Exception as exc:  # each driver raises its own types
            raise ConnectorError(clean(exc)) from exc
        return self

    def __exit__(self, *_: object) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None

    def query(self, sql: str, params: Any = None) -> list[tuple]:
        cursor = self._conn.cursor()
        try:
            cursor.execute(sql, params) if params is not None else cursor.execute(sql)
            return list(cursor.fetchall())
        except Exception as exc:
            raise ConnectorError(clean(exc)) from exc
        finally:
            cursor.close()

    def table_ref(self, database: str, schema: str, name: str) -> exp.Table:
        return exp.table_(name, db=schema, catalog=database, quoted=True)

    def column_ref(self, column: str) -> exp.Column:
        return exp.column(column, quoted=True)

    def sample(self, database: str, schema: str, table: str, column: str, limit: int = 1000) -> list[Any]:
        """Up to `limit` distinct non-null values of one column."""
        col = self.column_ref(column)
        sql = (exp.select(col).distinct().from_(self.table_ref(database, schema, table))
               .where(exp.Not(this=exp.Is(this=col.copy(), expression=exp.Null()))).limit(limit)
               .sql(dialect=self.dialect))
        return [r[0] for r in self.query(sql)]

    def count_matching(self, database: str, schema: str, table: str, column: str, values: list[Any],
                       numeric: bool) -> int:
        """How many of `values` occur in a column (used to check a suggested join against real data)."""
        if not values:
            return 0
        return self.query(count_matching_sql(self, database, schema, table, column, values, numeric))[0][0]

    def distinct_ratio(self, database: str, schema: str, table: str, column: str, limit: int = 100_000) -> float:
        """Distinct values / non-null rows over at most `limit` rows: near 1.0 means the column is a key."""
        col = self.column_ref(column)
        inner = (exp.select(exp.alias_(col, "v")).from_(self.table_ref(database, schema, table))
                 .where(exp.Not(this=exp.Is(this=col.copy(), expression=exp.Null()))).limit(limit))
        sql = exp.select("COUNT(DISTINCT v)", "COUNT(*)").from_(inner.subquery("s")).sql(dialect=self.dialect)
        distinct, total = self.query(sql)[0]
        return (distinct / total) if total else 0.0


def _literal(value: Any, numeric: bool) -> exp.Expression:
    return exp.Literal.number(value) if numeric else exp.Literal.string(str(value))


def count_matching_sql(wh: "Warehouse", database: str, schema: str, table: str, column: str,
                       values: list[Any], numeric: bool) -> str:
    col = wh.column_ref(column)
    return (exp.select(exp.Count(this=exp.Distinct(expressions=[col])))
            .from_(wh.table_ref(database, schema, table))
            .where(exp.In(this=col.copy(), expressions=[_literal(v, numeric) for v in values]))
            .sql(dialect=wh.dialect))
