"""Map S-LAYER semantic formats to Flint semantic types and annotations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import pyarrow as pa
from s_layer_semantic_formats import (
    Additivity,
    BytesValue,
    CategoryValue,
    CurrencyValue,
    DurationValue,
    GeoValue,
    NumberValue,
    PercentageValue,
    QuantityValue,
    ScoreValue,
    SLayerBlock,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "FLINT_SEMANTIC_TYPES",
    "FLINT_VERSION",
    "FieldType",
    "Grain",
    "ValueForm",
    "field_display_names",
    "map_field",
    "semantic_types",
]

FLINT_VERSION = "1.0.1"
"""The flint-chart release the mapping was written and checked against."""

Grain = Literal["second", "minute", "hour", "day", "week", "month", "quarter", "year"]
"""A time grain, as the vocabulary's ``time.grain`` and semolina's ``.grain()`` name them."""

ValueForm = Literal[
    "as_is",
    "percent_to_fraction",
    "year",
    "year_quarter",
    "year_month",
    "date",
    "datetime",
]
"""
How a column's values must be written into the chart's JSON rows for its Flint type.

- ``as_is``: unchanged (numbers, labels, flags, identifiers).
- ``percent_to_fraction``: a 0-100 percentage divided by 100.
- ``year``: the year as an integer, ``2024``.
- ``year_quarter``: ``"2024-Q1"``.
- ``year_month``: ``"2024-01"``.
- ``date``: an ISO 8601 date, ``"2024-01-15"``.
- ``datetime``: an ISO 8601 timestamp, ``"2024-01-15T14:30:00"``.
"""

FLINT_SEMANTIC_TYPES: frozenset[str] = frozenset(
    {
        "Amount",
        "Boolean",
        "Category",
        "City",
        "Count",
        "Country",
        "Date",
        "DateTime",
        "Duration",
        "ID",
        "Latitude",
        "Longitude",
        "Number",
        "Percentage",
        "Price",
        "Quantity",
        "Region",
        "Score",
        "State",
        "Year",
        "YearMonth",
        "YearQuarter",
        "ZipCode",
    }
)
"""Every Flint semantic type :func:`map_field` can return. CI checks each is in Flint's registry."""

_GEO_TYPES: Mapping[str, str] = {
    "country": "Country",
    "region": "Region",
    "state": "State",
    "city": "City",
    "postal_code": "ZipCode",
    "latitude": "Latitude",
    "longitude": "Longitude",
}

# Flint prints these spellings as compact suffixes; the vocabulary's short codes it doesn't know.
_DURATION_UNITS: Mapping[str, str] = {
    "ms": "ms",
    "s": "seconds",
    "min": "minutes",
    "h": "hours",
    "d": "days",
}

# Day and coarser grains: the Flint type and the form its values take.
_PERIOD_TYPES: Mapping[str, tuple[str, ValueForm]] = {
    "year": ("Year", "year"),
    "quarter": ("YearQuarter", "year_quarter"),
    "month": ("YearMonth", "year_month"),
    # A week is drawn as the date of its Monday. YearWeek wants "2024-W01" labels and treats them
    # as a label sequence, not a time axis.
    "week": ("Date", "date"),
    "day": ("Date", "date"),
}


@dataclass(frozen=True, kw_only=True)
class FieldType:
    """
    The Flint semantic type and annotation for one result column.

    ``semantic_type`` and the annotation fields go into the Flint input's ``semantic_types``,
    ``display_name`` into ``field_display_names``, and ``value_form`` says how the server writes
    the column's values into the JSON rows. ``fallback`` is true when the column had no
    ``s_layer`` block and was typed from its Arrow type instead.
    """

    semantic_type: str
    value_form: ValueForm = "as_is"
    unit: str | None = None
    intrinsic_domain: tuple[float, float] | None = None
    sort_order: tuple[str, ...] | None = None
    display_name: str | None = None
    fallback: bool = False

    def flint_annotation(self) -> str | dict[str, object]:
        """
        Return this column's entry in Flint's ``semantic_types``.

        A bare type name when there is nothing to annotate, else a ``SemanticAnnotation``
        object with only the keys that are set.

        Example:
            .. code-block:: python

                FieldType(semantic_type="Count").flint_annotation()  # "Count"
                FieldType(semantic_type="Amount", unit="USD").flint_annotation()
                # {"semanticType": "Amount", "unit": "USD"}
        """
        annotation: dict[str, object] = {}
        if self.unit is not None:
            annotation["unit"] = self.unit
        if self.intrinsic_domain is not None:
            annotation["intrinsicDomain"] = list(self.intrinsic_domain)
        if self.sort_order is not None:
            annotation["sortOrder"] = list(self.sort_order)
        if not annotation:
            return self.semantic_type
        return {"semanticType": self.semantic_type, **annotation}


def map_field(
    block: SLayerBlock | None,
    arrow_type: pa.DataType,
    *,
    grain: Grain | None = None,
    additivity: Additivity | None = None,
    aggregation: str | None = None,
    label: str | None = None,
) -> FieldType:
    """
    Choose the Flint type and annotation for one result column.

    Args:
        block: The member's ``s_layer`` block, or ``None`` when it has none.
        arrow_type: The column's type in the query result. Used only when ``block`` is ``None``.
        grain: The grain the query asked for (semolina's ``.grain()``). It wins over the block's
            declared ``time.grain``, since the result column holds the re-bucketed values.
        additivity: The additivity the semantic definition declares (``NON ADDITIVE BY``, dbt
            ``non_additive_dimension``, the metric's aggregation type). Used only when the block
            states none. It decides between ``Amount`` and ``Price`` for currency.
        aggregation: The metric's aggregation function, such as ``"count"``. Used only when
            ``block`` is ``None``: an integer ``count`` metric falls back to ``Count``.
        label: The member's label from the platform's own label slot. Wins over the block's
            ``label``, which is only for platforms that have no slot.

    Returns:
        The column's :class:`FieldType`.

    Example:
        .. code-block:: python

            block = SLayerBlock.model_validate({"value": {"kind": "currency", "currency": "EUR"}})
            map_field(block, pa.decimal128(18, 2), label="Revenue").flint_annotation()
            # {"semanticType": "Amount", "unit": "EUR"}
    """
    display_name = label if label is not None else block.label if block is not None else None
    if block is None:
        field = _from_arrow_type(arrow_type, grain=grain, aggregation=aggregation)
        return _with(field, display_name=display_name, fallback=True)
    effective_grain = grain or (block.time.grain if block.time is not None else None)
    return _with(
        _from_block(block, grain=effective_grain, additivity=additivity),
        display_name=display_name,
    )


def semantic_types(fields: Mapping[str, FieldType]) -> dict[str, str | dict[str, object]]:
    """Flint's ``semantic_types`` for a result, keyed by column name."""
    return {name: field.flint_annotation() for name, field in fields.items()}


def field_display_names(fields: Mapping[str, FieldType]) -> dict[str, str]:
    """Flint's ``field_display_names`` for a result: the columns that have a label."""
    return {
        name: field.display_name for name, field in fields.items() if field.display_name is not None
    }


def _with(field: FieldType, *, display_name: str | None, fallback: bool = False) -> FieldType:
    return FieldType(
        semantic_type=field.semantic_type,
        value_form=field.value_form,
        unit=field.unit,
        intrinsic_domain=field.intrinsic_domain,
        sort_order=field.sort_order,
        display_name=display_name,
        fallback=fallback,
    )


def _from_block(
    block: SLayerBlock, *, grain: Grain | None, additivity: Additivity | None
) -> FieldType:
    value = block.value
    match block.kind:
        case "number":
            assert isinstance(value, NumberValue)
            return FieldType(semantic_type="Number", unit=value.unit)
        case "count":
            return FieldType(semantic_type="Count")
        case "currency":
            assert isinstance(value, CurrencyValue)
            effective = block.additivity or additivity
            semantic_type = "Price" if effective == "non_additive" else "Amount"
            return FieldType(semantic_type=semantic_type, unit=value.currency)
        case "percentage":
            assert isinstance(value, PercentageValue)
            # Flint formats a percentage only when a domain is set, and it still guesses 0-1
            # against 0-100 from the data, so the values always go out as fractions.
            return FieldType(
                semantic_type="Percentage",
                intrinsic_domain=(0, 1),
                value_form="percent_to_fraction" if value.scale == "percent" else "as_is",
            )
        case "duration":
            assert isinstance(value, DurationValue)
            return FieldType(semantic_type="Duration", unit=_DURATION_UNITS[value.unit])
        case "bytes":
            assert isinstance(value, BytesValue)
            return FieldType(semantic_type="Quantity", unit=value.unit)
        case "quantity":
            assert isinstance(value, QuantityValue)
            return FieldType(semantic_type="Quantity", unit=value.unit)
        case "score":
            assert isinstance(value, ScoreValue)
            return FieldType(semantic_type="Score", intrinsic_domain=value.range)
        case "category":
            assert isinstance(value, CategoryValue)
            order = tuple(value.order) if value.order is not None else None
            return FieldType(semantic_type="Category", sort_order=order)
        case "geo":
            assert isinstance(value, GeoValue)
            return FieldType(semantic_type=_GEO_TYPES[value.level])
        case "date":
            return _temporal(grain, default="date")
        case "datetime":
            return _temporal(grain, default="datetime")
        case "identifier":
            return FieldType(semantic_type="ID")
        case "boolean":
            return FieldType(semantic_type="Boolean")


def _temporal(grain: Grain | None, *, default: Literal["date", "datetime"]) -> FieldType:
    if grain is not None and grain in _PERIOD_TYPES:
        semantic_type, value_form = _PERIOD_TYPES[grain]
        return FieldType(semantic_type=semantic_type, value_form=value_form)
    if default == "date":
        # A date has no time of day, so a sub-day grain leaves it a date.
        return FieldType(semantic_type="Date", value_form="date")
    # Hour and finer, or a timestamp with no grain: a continuous time axis. Flint's DateTime
    # reads ISO 8601 strings; its Timestamp type means epoch numbers.
    return FieldType(semantic_type="DateTime", value_form="datetime")


def _from_arrow_type(
    arrow_type: pa.DataType, *, grain: Grain | None, aggregation: str | None
) -> FieldType:
    if pa.types.is_date(arrow_type):
        return _temporal(grain, default="date")
    if pa.types.is_timestamp(arrow_type):
        return _temporal(grain, default="datetime")
    if pa.types.is_boolean(arrow_type):
        return FieldType(semantic_type="Boolean")
    if pa.types.is_integer(arrow_type):
        if aggregation is not None and aggregation.lower().startswith("count"):
            return FieldType(semantic_type="Count")
        return FieldType(semantic_type="Number")
    if pa.types.is_floating(arrow_type) or pa.types.is_decimal(arrow_type):
        return FieldType(semantic_type="Number")
    return FieldType(semantic_type="Category")
