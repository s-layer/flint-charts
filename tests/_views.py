"""Semantic views and query results for the query, chart and toolset tests."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from semolina import Dimension, Metric, SemanticView

from tests._arrow import table

if TYPE_CHECKING:
    import pyarrow as pa
    from semolina import Query


class Sales(SemanticView, view="analytics.sales"):
    """Orders and revenue by region."""

    revenue = Metric[float](
        label="Revenue",
        description="Booked revenue",
        semantic_format={
            "value": {"kind": "currency", "currency": "USD"},
            "aggregation": {"additivity": "additive"},
        },
    )
    margin = Metric[float](
        semantic_format={
            "value": {"kind": "percentage", "scale": "percent"},
            "aggregation": {"additivity": "non_additive"},
        },
    )
    balance = Metric[float](
        semantic_format={
            "value": {"kind": "currency", "currency": "USD"},
            "aggregation": {"additivity": "semi_additive", "by": ["ordered_at"]},
        },
    )
    region = Dimension[str](label="Region", semantic_format={"value": {"kind": "category"}})
    ordered_at = Dimension[dt.date](semantic_format={"value": {"kind": "date"}})


MONTHS = [dt.date(2024, m, 1) for m in (1, 2, 3)]


def monthly(query: Query) -> pa.Table:
    """A month-by-region result with the columns ``query`` selects, upper-cased like Snowflake."""
    data: dict[str, list[object]] = {
        "ordered_at__month": [m for m in MONTHS for _ in range(2)],
        "region": ["EU", "US"] * 3,
        "revenue": [100.0, 80.0, 120.0, 90.0, 130.0, 95.0],
        "margin": [12.0, 18.0, 11.5, 17.0, 13.0, 19.5],
        "balance": [1000.0, 800.0, 1100.0, 850.0, 1200.0, 900.0],
    }
    names = [f.name for f in (*query.selected_dimensions, *query.selected_metrics)]
    return table({str(name).upper(): data[str(name)] for name in names})
