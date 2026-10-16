"""Checking a metric definition before it is proposed.

A metric is an aggregate over one approved table, with an optional filter,
written in that warehouse's SQL dialect: for example `sum(net_amount)` with
the filter `status = 'complete'`. The check is done by parsing, not by
running anything: one expression, at least one aggregate in the measure and
none in the filter, no subqueries, and only columns the table has.
"""

import sqlglot
from sqlglot import exp


class MetricError(ValueError):
    """The definition is not acceptable; the message is shown to the person."""


def _parse(text: str, dialect: str, what: str) -> exp.Expression:
    try:
        select = sqlglot.parse_one(f"SELECT {text}" if what == "measure" else f"SELECT 1 WHERE {text}",
                                   read=dialect)
    except sqlglot.errors.ParseError as exc:
        raise MetricError(f"The {what} is not valid SQL: {str(exc).splitlines()[0]}") from None
    if not isinstance(select, exp.Select) or select.args.get("from") or select.args.get("from_"):
        raise MetricError(f"The {what} must be a single expression.")
    if what == "measure":
        if len(select.expressions) != 1:
            raise MetricError("The measure must be one expression, such as sum(net_amount).")
        return select.expressions[0]
    return select.args["where"].this


def _check_columns(node: exp.Expression, columns: set[str], what: str) -> None:
    if node.find(exp.Select, exp.Subquery):
        raise MetricError(f"The {what} cannot contain a subquery.")
    for col in node.find_all(exp.Column):
        if col.table:
            raise MetricError(f"Refer to columns by name only in the {what} (not {col.sql()}).")
        if col.name.lower() not in columns:
            raise MetricError(f"The table has no column named {col.name}.")


def validate(measure: str, filter: str | None, dialect: str, columns: list[str]) -> dict:
    """Normalised measure and filter SQL, or MetricError."""
    names = {c.lower() for c in columns}
    m = _parse(measure, dialect, "measure")
    _check_columns(m, names, "measure")
    if not m.find(exp.AggFunc):
        raise MetricError("The measure must aggregate, for example sum(amount) or count(distinct customer_id).")
    out = {"measure": m.sql(dialect=dialect), "filter": None}
    if filter and filter.strip():
        f = _parse(filter, dialect, "filter")
        _check_columns(f, names, "filter")
        if f.find(exp.AggFunc):
            raise MetricError("The filter cannot aggregate; it limits which rows are counted.")
        out["filter"] = f.sql(dialect=dialect)
    return out
