"""
Run a semolina query for a chart and keep its result, telling the model only what it holds.

The rows stay on the server. The model gets a summary (row count, each column's kind, type
and range, a few sample rows) and a ``result_id`` to chart.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, TypeAlias

import orjson
from semolina.fields import GrainedDimension
from semolina.spec import build_query

from s_layer_flint_charts._grain import Metric
from s_layer_flint_charts._mapping import map_field
from s_layer_flint_charts._rows import DEFAULT_ROW_CAP, chart_rows
from s_layer_flint_charts._store import Column, StoredResult

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping

    import pyarrow as pa
    from semolina import Field, Query, SemanticView

    from s_layer_flint_charts._store import ChartSession

__all__ = ["Fetch", "result_columns", "run_query", "store_result", "summarize"]

Fetch: TypeAlias = "Callable[[Query], Awaitable[pa.Table]]"
"""Runs a query and returns its result as an Arrow table."""

_SAMPLE_ROWS = 5
_SAMPLE_VALUES = 8


async def _fetch_async(query: Query) -> pa.Table:
    async with await query.aexecute() as cursor:
        return await cursor.fetch_arrow_table()


async def run_query(
    session: ChartSession,
    model: type[SemanticView],
    spec: Mapping[str, Any],
    *,
    cap: int = DEFAULT_ROW_CAP,
    fetch: Fetch | None = None,
) -> dict[str, object]:
    """
    Run a query described as data, keep its result in ``session`` and summarise it.

    The query asks for one row more than ``cap``, so a result that would be cut is known to be
    cut without fetching all of it.

    Args:
        session: The conversation's session.
        model: The semantic view to query.
        spec: The query as semolina's query spec (``metrics``, ``dimensions``, ``where``,
            ``order_by``, ``limit``); see :func:`semolina.spec.build_query`.
        cap: The most rows a chart may draw.
        fetch: Runs the query. By default the query runs on its async engine.

    Returns:
        The summary from :func:`summarize`.

    Raises:
        semolina.SemolinaSpecError: The spec names a field the view does not have, or is
            otherwise malformed. Its message is meant for whoever wrote the spec.
    """
    query = build_query(model, spec)
    if query.limit_value is None or query.limit_value > cap:
        query = query.limit(cap + 1)
    table = await (fetch or _fetch_async)(query)
    result = store_result(session, query, table, view=model._view_name, cap=cap)
    return summarize(result)


def store_result(
    session: ChartSession, query: Query, table: pa.Table, *, view: str, cap: int = DEFAULT_ROW_CAP
) -> StoredResult:
    """
    Convert a query's result into chart rows once, and keep it under a new ``result_id``.

    Args:
        session: The conversation's session.
        query: The query that produced ``table``.
        table: Its result.
        view: The semantic view's name, for the chart's source line.
        cap: The most rows a chart may draw.

    Returns:
        The :class:`StoredResult`.
    """
    table, columns = result_columns(query, table)
    rows = chart_rows(table, {name: column.field_type for name, column in columns.items()}, cap=cap)
    result = StoredResult(
        result_id=session.new_result_id(),
        view=view,
        columns=columns,
        rows=rows,
        queried_at=datetime.datetime.now(datetime.UTC),
    )
    session.add_result(result)
    return result


def result_columns(query: Query, table: pa.Table) -> tuple[pa.Table, dict[str, Column]]:
    """
    Describe each result column from the query field it holds.

    Result columns are matched to the query's fields by name, ignoring case (a warehouse may
    fold the aliases), and renamed to the fields' names.

    Args:
        query: The query.
        table: Its result.

    Returns:
        The table with its columns named after the fields, and a :class:`Column` per field.

    Raises:
        ValueError: A column of the result matches no field of the query, or two columns
            match one field.
    """
    fields: dict[str, Field[Any]] = {
        _name(field): field for field in (*query.selected_dimensions, *query.selected_metrics)
    }
    by_folded = {name.casefold(): name for name in fields}
    names: list[str] = []
    for name in table.column_names:
        match = name if name in fields else by_folded.get(name.casefold())
        if match is None:
            raise ValueError(f"result column {name!r} is not a field of the query")
        if match in names:
            raise ValueError(f"the result has more than one column for {match!r}")
        names.append(match)
    table = table.rename_columns(names)
    metric_names = {_name(metric) for metric in query.selected_metrics}
    columns: dict[str, Column] = {}
    for name in names:
        field = fields[name]
        block = field.semantic_format
        grain = field.unit if isinstance(field, GrainedDimension) else None
        metric = None
        if name in metric_names:
            by: set[str] = set(block.aggregation.by or ()) if block and block.aggregation else set()
            metric = Metric(
                additivity=block.additivity if block is not None else None,
                non_additive_by=frozenset(
                    other for other in names if other in by or _base_name(fields[other]) in by
                ),
            )
        columns[name] = Column(
            name=name,
            field_type=map_field(block, table.column(name).type, grain=grain, label=field.label),
            metric=metric,
            description=field.description,
        )
    return table, columns


def _name(field: Field[Any]) -> str:
    if field.name is None:  # pragma: no cover - a query only holds fields bound to a view
        raise ValueError(f"{field!r} is not bound to a semantic view")
    return field.name


def _base_name(field: Field[Any]) -> str:
    return _name(field.base) if isinstance(field, GrainedDimension) else _name(field)


def _range(values: list[object]) -> tuple[object, object] | None:
    """The smallest and largest of a column of numbers, else ``None``."""
    numbers = [
        value for value in values if isinstance(value, int | float) and not isinstance(value, bool)
    ]
    if numbers and len(numbers) == len(values):
        return min(numbers), max(numbers)
    return None


def summarize(result: StoredResult, *, samples: int = _SAMPLE_ROWS) -> dict[str, object]:
    """
    What the model learns about a result: enough to choose a chart, never the full rows.

    Each column has its kind, Flint type and label; a numeric or temporal column its range; a
    dimension its number of distinct values and a few of them. Values are JSON-ready.
    """
    rows = result.rows.rows
    columns: list[dict[str, object]] = []
    for name, column in result.columns.items():
        field_type = result.rows.fields.get(name, column.field_type)
        entry: dict[str, object] = {
            "name": name,
            "kind": column.kind,
            "type": field_type.semantic_type,
        }
        if field_type.display_name:
            entry["label"] = field_type.display_name
        if field_type.unit:
            entry["unit"] = field_type.unit
        if column.description:
            entry["description"] = column.description
        values = [row[name] for row in rows if row[name] is not None]
        bounds = _range(values)
        if bounds is not None:
            entry["min"], entry["max"] = bounds
        if column.kind == "dimension":
            distinct = list(dict.fromkeys(values))
            entry["distinct_values"] = len(distinct)
            entry["sample_values"] = distinct[:_SAMPLE_VALUES]
        columns.append(entry)
    summary: dict[str, object] = {
        "result_id": result.result_id,
        "view": result.view,
        "rows": len(rows),
        "columns": columns,
        "sample_rows": rows[:samples],
    }
    if result.rows.capped:
        summary["capped"] = (
            f"the query returned more than {len(rows)} rows and was cut; filter it or use a "
            "coarser grain before charting it"
        )
    return orjson.loads(orjson.dumps(summary))
