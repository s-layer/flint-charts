"""Turn a query result into the JSON rows a Flint chart draws."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import orjson
import pyarrow as pa
import pyarrow.compute as pc

from s_layer_flint_charts._mapping import fit_to_values

if TYPE_CHECKING:
    from collections.abc import Mapping

    from s_layer_flint_charts._mapping import FieldType, ValueForm

__all__ = ["DEFAULT_ROW_CAP", "ChartRows", "UnsupportedColumnError", "chart_rows"]

DEFAULT_ROW_CAP = 5_000
"""Rows a charted result keeps. Flint's own validation limit is 100,000."""

# pyarrow-stubs types compute functions too narrowly for arrays (some only accept expressions)
# and leaves parts of pa.table unknown, so those calls go through untyped handles and each
# result is typed where it is used.
_pc: Any = pc
_pa: Any = pa

MAX_SAFE_INTEGER = 2**53 - 1
"""The largest integer a JavaScript number holds exactly."""


class UnsupportedColumnError(TypeError):
    """A result column has an Arrow type that has no JSON form for a chart."""


@dataclass(frozen=True, kw_only=True)
class ChartRows:
    """
    A result as JSON-ready rows, with the column types fitted to the values.

    ``fields`` is the input mapping after :func:`fit_to_values`, so a percentage whose values
    leave ``[0, 1]`` arrives as ``PercentageChange``. ``capped`` is true when the result had
    more rows than the cap and was cut; a capped result should not be charted.
    """

    rows: list[dict[str, object]]
    fields: dict[str, FieldType]
    capped: bool
    total_rows: int

    def to_json(self) -> bytes:
        """The rows as JSON bytes, the same bytes for the validator and the browser."""
        return orjson.dumps(self.rows)


def chart_rows(
    table: pa.Table, fields: Mapping[str, FieldType], *, cap: int = DEFAULT_ROW_CAP
) -> ChartRows:
    """
    Convert a query result into the rows Flint draws.

    Each column is written in its field's ``value_form`` (a year as an integer, a month as
    ``"2024-01"``, a 0-100 percentage as a fraction). Decimals become floats, and an integer
    column holding a value a JavaScript number cannot hold exactly becomes strings. Dates and
    timestamps are written as ISO 8601 by orjson. A column with no entry in ``fields`` is
    passed through with the same casts.

    Args:
        table: The query result.
        fields: The Flint type of each column, from :func:`map_field`.
        cap: The most rows to keep. A longer result is cut and marked ``capped``.

    Returns:
        The :class:`ChartRows`.

    Raises:
        UnsupportedColumnError: A column is binary, a duration, nested or of another type with
            no JSON form.
    """
    total_rows = table.num_rows
    capped = total_rows > cap
    if capped:
        table = table.slice(0, cap)
    columns: dict[str, pa.Array[Any]] = {}
    fitted: dict[str, FieldType] = dict(fields)
    for name in table.column_names:
        column = table.column(name).combine_chunks()
        field = fields.get(name)
        column = _json_safe(name, column)
        if field is not None:
            column = _apply_value_form(column, field.value_form)
            fitted[name] = _fit(field, column)
        columns[name] = column
    rows: list[dict[str, object]] = (
        _pa.table(columns).to_pylist() if columns else [{} for _ in range(table.num_rows)]
    )
    return ChartRows(rows=rows, fields=fitted, capped=capped, total_rows=total_rows)


def _json_safe(name: str, column: pa.Array[Any]) -> pa.Array[Any]:
    kind = column.type
    if pa.types.is_dictionary(kind):
        return _json_safe(name, cast("Any", column).dictionary_decode())
    if pa.types.is_decimal(kind):
        return _pc.cast(column, pa.float64())
    if pa.types.is_integer(kind):
        if column.null_count == len(column):
            return column
        bounds = _pc.min_max(column)
        low, high = bounds["min"].as_py(), bounds["max"].as_py()
        if low < -MAX_SAFE_INTEGER or high > MAX_SAFE_INTEGER:
            return _pc.cast(column, pa.string())
        return column
    if (
        pa.types.is_floating(kind)
        or pa.types.is_boolean(kind)
        or pa.types.is_date(kind)
        or pa.types.is_timestamp(kind)
        or pa.types.is_null(kind)
    ):
        return column
    if pa.types.is_string(kind) or pa.types.is_large_string(kind):
        return column
    if pa.types.is_string_view(kind):
        return _pc.cast(column, pa.string())
    raise UnsupportedColumnError(f"column {name!r} has type {kind}, which a chart cannot draw")


def _apply_value_form(column: pa.Array[Any], value_form: ValueForm) -> pa.Array[Any]:
    if value_form == "as_is" or value_form == "datetime":
        return column
    if value_form == "percent_to_fraction":
        return _pc.divide(_pc.cast(column, pa.float64()), 100.0)
    if not (pa.types.is_date(column.type) or pa.types.is_timestamp(column.type)):
        # A period already written as text (or a year as a number) is left as the query
        # returned it.
        return column
    column = _local(column)
    match value_form:
        case "date":
            return _pc.cast(column, pa.date32()) if pa.types.is_timestamp(column.type) else column
        case "year":
            return _pc.cast(_pc.year(column), pa.int32())
        case "year_month":
            return _pc.strftime(column, format="%Y-%m")
        case "year_quarter":
            return _pc.binary_join_element_wise(
                _pc.cast(_pc.year(column), pa.string()),
                _pc.cast(_pc.quarter(column), pa.string()),
                "-Q",
            )


def _local(column: pa.Array[Any]) -> pa.Array[Any]:
    """A zoned timestamp as wall-clock time in its zone, so its date is the local date."""
    kind = column.type
    if pa.types.is_timestamp(kind) and kind.tz is not None:
        return _pc.local_timestamp(column)
    return column


def _fit(field: FieldType, column: pa.Array[Any]) -> FieldType:
    if field.semantic_type != "Percentage" or column.null_count == len(column):
        return field
    bounds = _pc.min_max(column)
    low, high = bounds["min"].as_py(), bounds["max"].as_py()
    if not isinstance(low, int | float) or not isinstance(high, int | float):
        return field
    return fit_to_values(field, low, high)
