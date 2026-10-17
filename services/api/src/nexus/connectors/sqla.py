"""Warehouses reached through SQLAlchemy, the way OpenMetadata reaches them.

One engine per connection, built from the platform's own SQLAlchemy dialect and
driver; the catalog is read with SQLAlchemy's inspector (schemas, tables, views,
columns, comments, foreign keys), so each platform's dialect does the
platform-specific work. The connection test runs the same steps OpenMetadata
runs: check access, list schemas, list tables, list views, plus any
platform-specific check.

Approach and settings follow OpenMetadata 1.5 (Apache License 2.0); see NOTICE.
"""

import logging
from abc import abstractmethod
from typing import Any

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import URL, Engine
from sqlalchemy.engine.reflection import ObjectKind
from sqlalchemy.pool import NullPool
from sqlglot import exp

from nexus.connectors.base import (
    ColumnMeta,
    ConnectorError,
    ForeignKey,
    TableMeta,
    Warehouse,
    clean,
    normalise_type,
    schema_allowed,
)
from nexus.connectors.spec import TestResult

log = logging.getLogger("nexus.connectors")


def _n(count: int, noun: str) -> str:
    return f"{count} {noun}{'' if count == 1 else 's'}"


def _supports_autocommit(engine: Engine) -> bool:
    # Transactional dialects list their isolation levels without a live connection;
    # the others raise, and do not hold locks between statements anyway.
    try:
        return "AUTOCOMMIT" in engine.dialect.get_isolation_level_values(None)  # type: ignore[arg-type]
    except Exception:
        return False


class SqlAlchemyWarehouse(Warehouse):
    #: Schemas that describe the platform rather than the customer's data (compared case-insensitively).
    system_schemas: frozenset[str] = frozenset()
    #: Whether a table is addressed database.schema.table (False: schema.table).
    three_part_names: bool = True
    #: The cheapest statement that proves the session works.
    check_access_sql: str = "SELECT 1"
    #: Extra test steps: name -> statement.
    extra_checks: dict[str, str] = {}

    _engine: Engine | None = None

    @abstractmethod
    def url(self) -> URL: ...

    def connect_args(self) -> dict[str, Any]:
        return {}

    def engine_kwargs(self) -> dict[str, Any]:
        return {}

    def database_label(self) -> str:
        """The name shown as the table's database (the first part of its key)."""
        return self.settings.get("database") or self.spec.kind

    # Connection ------------------------------------------------------------

    def _connect(self):
        def build(**extra) -> Engine:
            return create_engine(self.url(), connect_args=self.connect_args(), poolclass=NullPool,
                                 **self.engine_kwargs(), **extra)

        engine = build()
        # Read-only sessions must not hold a transaction (and its locks) open while
        # the catalog is read, so autocommit wherever the dialect supports it.
        if _supports_autocommit(engine):
            engine.dispose()
            engine = build(isolation_level="AUTOCOMMIT")
        self._engine = engine
        return engine.connect()

    def __exit__(self, *exc: object) -> None:
        try:
            super().__exit__(*exc)
        finally:
            if self._engine is not None:
                self._engine.dispose()
                self._engine = None

    def query(self, sql: str, params: Any = None) -> list[tuple]:
        try:
            result = self._conn.exec_driver_sql(sql, params) if params else self._conn.exec_driver_sql(sql)
            return [tuple(r) for r in result.fetchall()]
        except Exception as exc:
            raise ConnectorError(clean(exc)) from exc

    # Names -----------------------------------------------------------------

    def _raw(self, name: str) -> str:
        """The name as the database stores it. Dialects such as Oracle's report
        upper-case names in lower case; quoting needs the stored form back."""
        dialect = self._engine.dialect if self._engine is not None else None
        if dialect is None or not getattr(dialect, "requires_name_normalize", False):
            return name
        return dialect.denormalize_name(name)

    def table_ref(self, database: str, schema: str, name: str) -> exp.Table:
        if self.three_part_names:
            return exp.table_(self._raw(name), db=self._raw(schema), catalog=database, quoted=True)
        return exp.table_(self._raw(name), db=self._raw(schema), quoted=True)

    def column_ref(self, column: str) -> exp.Column:
        return exp.column(self._raw(column), quoted=True)

    # Catalog ---------------------------------------------------------------

    def schemas(self) -> list[str]:
        try:
            names = inspect(self._conn).get_schema_names()
        except Exception as exc:
            raise ConnectorError(clean(exc)) from exc
        system = {s.lower() for s in self.system_schemas}
        return [s for s in names if s.lower() not in system and schema_allowed(self.settings, s)]

    def tables(self) -> list[TableMeta]:
        insp = inspect(self._conn)
        out: list[TableMeta] = []
        for schema in self.schemas():
            try:
                tables = set(insp.get_table_names(schema=schema))
                try:
                    views = set(insp.get_view_names(schema=schema))
                except NotImplementedError:
                    views = set()
                columns = self._multi(insp.get_multi_columns, insp.get_columns, schema, tables | views)
                comments = self._multi(insp.get_multi_table_comment, insp.get_table_comment, schema,
                                       tables | views, default={})
            except ConnectorError:
                raise
            except Exception as exc:
                raise ConnectorError(f"Could not read schema {schema}: {clean(exc)}") from exc
            for name in sorted(tables | views):
                cols = columns.get(name) or []
                out.append(TableMeta(
                    database=self.database_label(), schema=schema, name=name,
                    kind="view" if name in views else "table",
                    columns=tuple(ColumnMeta(
                        name=c["name"], data_type=normalise_type(str(c["type"])), raw_type=str(c["type"]),
                        nullable=bool(c.get("nullable", True)), ordinal=i + 1, comment=c.get("comment") or "")
                        for i, c in enumerate(cols)),
                    comment=(comments.get(name) or {}).get("text") or "",
                ))
        return out

    def _multi(self, multi_fn, single_fn, schema: str, names: set[str], default=None) -> dict[str, Any]:
        """Reflect many tables at once where the dialect can, else one by one,
        skipping (not failing on) a table the role may not read."""
        if not names:
            return {}
        try:
            found = multi_fn(schema=schema, kind=ObjectKind.ANY)
            return {key[1]: value for key, value in found.items() if key[1] in names}
        except NotImplementedError:
            if default is not None:
                return {}
        except Exception as exc:  # some third-party dialects only implement the single-table call
            log.debug("bulk reflection failed for %s, reading tables one by one: %s", schema, exc)
        out = {}
        for name in names:
            try:
                out[name] = single_fn(name, schema=schema)
            except NotImplementedError:
                return {}
            except Exception:
                out[name] = default
        return out

    def foreign_keys(self) -> list[ForeignKey]:
        insp = inspect(self._conn)
        out: list[ForeignKey] = []
        for schema in self.schemas():
            try:
                found = insp.get_multi_foreign_keys(schema=schema)
            except Exception as exc:  # keys are a bonus; a schema without them is still read
                log.debug("foreign keys unavailable for %s: %s", schema, exc)
                continue
            for (_, table), keys in found.items():
                for fk in keys:
                    if len(fk["constrained_columns"]) != 1:
                        continue
                    ref_schema = fk.get("referred_schema") or schema
                    out.append(ForeignKey(
                        f"{self.database_label()}.{schema}.{table}".lower(), fk["constrained_columns"][0],
                        f"{self.database_label()}.{ref_schema}.{fk['referred_table']}".lower(),
                        fk["referred_columns"][0], fk.get("name") or ""))
        return out

    # Connection test -------------------------------------------------------

    def test(self) -> TestResult:
        steps: dict[str, str] = {}

        def step(name: str, fn) -> Any:
            try:
                value = fn()
                steps[name] = "passed"
                return value
            except Exception as exc:
                steps[name] = f"failed: {clean(exc)}"
                return None

        step("Check access", lambda: self.query(self.check_access_sql))
        schemas = step("List schemas", self.schemas) or []
        insp = inspect(self._conn)
        first = schemas[0] if schemas else None
        tables = step("List tables", lambda: sum(len(insp.get_table_names(schema=s)) for s in schemas))
        step("List views", lambda: len(insp.get_view_names(schema=first)) if first else 0)
        for name, sql in self.extra_checks.items():
            step(name, lambda sql=sql: self.query(sql))

        failed = [n for n, v in steps.items() if v != "passed"]
        if "Check access" in failed:
            return TestResult(False, f"Could not connect: {steps['Check access'].removeprefix('failed: ')}", steps)
        if not schemas:
            return TestResult(False, "Connected, but no schemas are visible to this user. Grant it read access, "
                                     "or check the schema filters.", steps)
        if failed:
            return TestResult(False, f"Connected, but these checks failed: {', '.join(failed)}.", steps)
        return TestResult(True, f"Connected. {_n(len(schemas), 'schema')} and {_n(tables or 0, 'table')} visible.", steps)
