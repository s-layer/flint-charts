"""
Flint inputs built from query results, checked by Flint itself in ts/test/flint-inputs.test.ts.

Each case runs a small result through :func:`chart_rows` and :func:`check_grain` and writes the
Flint ``ChartAssemblyInput`` the server would send. The Vitest suite assembles each input with
Flint and checks that a guarded chart draws without Flint merging rows, and that a chart the
guard refuses is one Flint would have merged. ``test_inputs_are_current`` keeps the committed
file in step; regenerate it with ``uv run python -m tests.test_flint_inputs``.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import orjson

from s_layer_flint_charts import (
    ChartRequest,
    FieldType,
    Metric,
    chart_rows,
    check_grain,
    field_display_names,
    percent_points,
    semantic_types,
)
from tests._arrow import table, where

if TYPE_CHECKING:
    import pyarrow as pa

INPUTS_FILE = Path(__file__).parent.parent / "ts" / "test" / "flint-inputs.json"

MONTHS = [dt.date(2024, m, 1) for m in (1, 2, 3)]
QUARTERS = [dt.date(2024, m, 1) for m in (1, 4, 7)]
MONTH = FieldType(semantic_type="YearMonth", value_form="year_month", display_name="Month")
QUARTER = FieldType(semantic_type="YearQuarter", value_form="year_quarter")
REGION = FieldType(semantic_type="Region", display_name="Region")
CHANNEL = FieldType(semantic_type="Category")
REVENUE = FieldType(semantic_type="Amount", unit="USD", display_name="Revenue")
MARGIN = FieldType(
    semantic_type="Percentage", intrinsic_domain=(0, 1), value_form="percent_to_fraction"
)
ORDERS = FieldType(semantic_type="Count")

ADDITIVE = Metric(additivity="additive")
RATIO = Metric(additivity="non_additive")


def _case(
    table: pa.Table,
    fields: dict[str, FieldType],
    request: ChartRequest,
    metrics: dict[str, Metric],
) -> dict[str, Any]:
    result = chart_rows(table, fields)
    check = check_grain(result.rows, request, metrics)
    values, fields, points = percent_points(check.rows, result.fields)
    flint_input = {
        "data": {"values": orjson.loads(orjson.dumps(values))},
        "semantic_types": semantic_types(fields),
        "field_display_names": field_display_names(fields),
        "chart_spec": {
            "chartType": request.chart_type,
            "encodings": {
                channel: {"field": column} if isinstance(column, str) else dict(column)
                for channel, column in request.encodings.items()
            },
            "chartProperties": check.chart_properties,
        },
    }
    percent_forms = {
        name: "points" if name in points else "fraction"
        for name, field in fields.items()
        if field.semantic_type in {"Percentage", "PercentageChange"}
    }
    return {"input": flint_input, "problems": list(check.problems), "percent_forms": percent_forms}


def build_inputs() -> dict[str, dict[str, Any]]:
    """Every case, keyed by name."""
    by_region = table(
        {
            "month": [m for m in MONTHS for _ in range(2)],
            "region": ["EU", "US"] * 3,
            "revenue": [100.0, 80.0, 120.0, 90.0, 130.0, 95.0],
            "margin": [12.0, 18.0, 11.5, 17.0, 13.0, 19.5],
        }
    )
    # US has no sales in February.
    by_quarter = table(
        {
            "quarter": [q for q in QUARTERS for _ in range(2)],
            "region": ["EU", "US"] * 3,
            "margin": [12.0, 18.0, 11.5, 17.0, 13.0, 19.5],
        }
    )
    gappy = where(by_region, [True, True, True, False, True, True])
    by_channel = table(
        {
            "month": [m for m in MONTHS for _ in range(4)],
            "region": ["EU", "EU", "US", "US"] * 3,
            "channel": ["web", "store"] * 6,
            "orders": list(range(12)),
        }
    )
    growth = table({"region": ["EU", "US", "APAC"], "growth": [-12.0, 35.0, 180.0]})
    return {
        "stacked_area_with_gap": _case(
            gappy,
            {"month": MONTH, "region": REGION, "revenue": REVENUE},
            ChartRequest(
                chart_type="Area Chart",
                encodings={"x": "month", "y": "revenue", "color": "region"},
            ),
            {"revenue": ADDITIVE, "margin": RATIO},
        ),
        "streamgraph_with_gap": _case(
            gappy,
            {"month": MONTH, "region": REGION, "revenue": REVENUE},
            ChartRequest(
                chart_type="Streamgraph",
                encodings={"x": "month", "y": "revenue", "color": "region"},
            ),
            {"revenue": ADDITIVE, "margin": RATIO},
        ),
        "margin_lines_by_quarter": _case(
            by_quarter,
            {"quarter": QUARTER, "region": REGION, "margin": MARGIN},
            ChartRequest(
                chart_type="Line Chart",
                encodings={"x": "quarter", "y": "margin", "color": "region"},
            ),
            {"margin": RATIO},
        ),
        "growth_bars": _case(
            growth,
            {"region": REGION, "growth": MARGIN},
            ChartRequest(
                chart_type="Bar Chart",
                encodings={"x": "region", "y": "growth", "color": "region"},
            ),
            {"growth": RATIO},
        ),
        "revenue_pie": _case(
            where(by_region, [True, True] + [False] * 4),  # January
            {"month": MONTH, "region": REGION, "revenue": REVENUE},
            ChartRequest(chart_type="Pie Chart", encodings={"size": "revenue", "color": "region"}),
            {"revenue": ADDITIVE, "margin": RATIO},
        ),
        "orders_heatmap": _case(
            where(by_channel, [True, False] * 6),  # web
            {"month": MONTH, "region": REGION, "channel": CHANNEL, "orders": ORDERS},
            ChartRequest(
                chart_type="Heatmap",
                encodings={"x": "month", "y": "region", "color": "orders"},
            ),
            {"orders": ADDITIVE},
        ),
        # Refused: channel is on no channel, so two rows share each cell.
        "orders_heatmap_channel_unplaced": _case(
            by_channel,
            {"month": MONTH, "region": REGION, "channel": CHANNEL, "orders": ORDERS},
            ChartRequest(
                chart_type="Heatmap",
                encodings={"x": "month", "y": "region", "color": "orders"},
            ),
            {"orders": ADDITIVE},
        ),
    }


def render() -> str:
    return json.dumps(build_inputs(), indent=2, sort_keys=True) + "\n"


def test_inputs_are_current() -> None:
    assert INPUTS_FILE.read_text() == render(), (
        "ts/test/flint-inputs.json is stale; run `uv run python -m tests.test_flint_inputs`"
    )


def test_cases_cover_both_percent_forms() -> None:
    forms = {form for case in build_inputs().values() for form in case["percent_forms"].values()}
    assert forms == {"fraction", "points"}


def test_cases_cover_both_verdicts() -> None:
    inputs = build_inputs()
    assert [name for name, case in inputs.items() if case["problems"]] == [
        "orders_heatmap_channel_unplaced"
    ]


if __name__ == "__main__":
    INPUTS_FILE.write_text(render())
