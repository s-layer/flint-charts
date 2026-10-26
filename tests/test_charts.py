"""Assembling Flint charts from stored results, and the receipt the model gets."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import orjson
import pytest
from semolina.spec import build_query

from s_layer_flint_charts import (
    CHART_TYPES,
    ChartSession,
    StoredResult,
    ValidationReport,
    assemble_chart,
    chart_rows_url,
    default_interactions,
    show_chart,
    store_result,
)
from tests._arrow import table
from tests._views import Sales, monthly

if TYPE_CHECKING:
    from collections.abc import Mapping

pytestmark = pytest.mark.anyio

LINES = {"x": "ordered_at__month", "y": "revenue", "color": "region"}


def stored(spec: Mapping[str, Any] | None = None, *, cap: int = 100) -> StoredResult:
    session = ChartSession()
    query = build_query(
        Sales,
        spec or {"metrics": ["revenue", "margin"], "dimensions": ["ordered_at__month", "region"]},
    )
    return store_result(session, query, monthly(query), view="analytics.sales", cap=cap)


class FakeValidator:
    def __init__(self, report: ValidationReport) -> None:
        self.report = report
        self.inputs: list[Mapping[str, object]] = []

    async def validate(self, flint_input: Mapping[str, object]) -> ValidationReport:
        self.inputs.append(flint_input)
        return self.report


def test_a_chart_is_assembled_from_the_result() -> None:
    result = stored()
    flint_input, problems = assemble_chart(
        result, chart_type="Line Chart", encodings=LINES, title="Revenue by month", theme="dark"
    )
    assert problems == ()
    assert flint_input is not None
    assert flint_input["data"] == {"values": result.rows.rows}
    assert flint_input["semantic_types"] == {
        "ordered_at__month": "YearMonth",
        "region": "Category",
        "revenue": {"semanticType": "Amount", "unit": "USD"},
        "margin": {"semanticType": "Percentage", "intrinsicDomain": [0, 1]},
    }
    assert flint_input["field_display_names"] == {"region": "Region", "revenue": "Revenue"}
    assert flint_input["chart_spec"] == {
        "chartType": "Line Chart",
        "title": "Revenue by month",
        "encodings": {
            "x": {"field": "ordered_at__month"},
            "y": {"field": "revenue"},
            "color": {"field": "region"},
        },
        "source": f"analytics.sales, queried {result.queried_at:%Y-%m-%d %H:%M} UTC",
    }
    assert flint_input["interaction_spec"] == {
        "interactions": [{"type": "inspect-index"}, {"type": "legend-toggle"}]
    }
    assert flint_input["theme_spec"] == "dark"


def test_a_subtitle_and_properties_are_passed_on() -> None:
    flint_input, _ = assemble_chart(
        stored(),
        chart_type="Area Chart",
        encodings=LINES,
        title="Revenue",
        subtitle="By region",
        chart_properties={"stackMode": "layered"},
        theme={"preset": "economist"},
    )
    assert flint_input is not None
    spec: Any = flint_input["chart_spec"]
    assert spec["subtitle"] == "By region"
    assert spec["chartProperties"] == {"stackMode": "layered"}
    assert flint_input["theme_spec"] == {"preset": "economist"}


@pytest.mark.parametrize(
    ("kwargs", "problem"),
    [
        ({"chart_type": "Pyramid"}, "'Pyramid' is not a chart type here"),
        ({"chart_type": "Bubble Chart"}, "'Bubble Chart' is not a chart type here"),
        ({"encodings": {}}, "put at least one column on a channel"),
        ({"encodings": {"x": "ordered_at__month", "y": "revenue"}}, "region"),
    ],
)
def test_a_chart_that_cannot_be_drawn_says_why(kwargs: dict[str, Any], problem: str) -> None:
    request: dict[str, Any] = {"chart_type": "Line Chart", "encodings": LINES, **kwargs}
    flint_input, problems = assemble_chart(stored(), title="Revenue", **request)
    assert flint_input is None
    assert any(problem in p for p in problems), problems


def test_a_capped_result_is_never_charted() -> None:
    flint_input, problems = assemble_chart(
        stored(cap=4), chart_type="Line Chart", encodings=LINES, title="Revenue"
    )
    assert flint_input is None
    assert "was cut" in problems[0]


def test_a_percentage_flint_would_misread_goes_out_as_points() -> None:
    query = build_query(Sales, {"metrics": ["margin"], "dimensions": ["region"]})
    growth = table({"region": ["EU", "US", "APAC"], "margin": [-12.0, 150.0, 240.0]})
    result = store_result(ChartSession(), query, growth, view="analytics.sales")
    flint_input, _ = assemble_chart(
        result, chart_type="Bar Chart", encodings={"x": "region", "y": "margin"}, title="Growth"
    )
    assert flint_input is not None
    values: Any = flint_input["data"]
    assert [row["margin"] for row in values["values"]] == [-12.0, 150.0, 240.0]
    types: Any = flint_input["semantic_types"]
    assert types["margin"] == {
        "semanticType": "PercentageChange",
        "intrinsicDomain": [-12.0, 240.0],
    }
    # The stored rows keep the fractions the summary showed.
    assert [row["margin"] for row in result.rows.rows] == [-0.12, 1.5, 2.4]


@pytest.mark.parametrize(
    ("chart_type", "has_color", "presets"),
    [
        ("Line Chart", False, ["inspect-index"]),
        ("Streamgraph", True, ["inspect-index", "legend-toggle"]),
        ("Bar Chart", True, ["click-highlight", "legend-toggle"]),
        ("Pie Chart", False, ["click-highlight"]),
        ("Heatmap", True, ["inspect"]),
        ("Scatter Plot", True, ["inspect"]),
    ],
)
def test_default_interactions(chart_type: str, has_color: bool, presets: list[str]) -> None:
    spec = default_interactions(chart_type, has_color=has_color)
    assert spec == {"interactions": [{"type": preset} for preset in presets]}


@pytest.mark.parametrize("chart_type", ["KPI Card", "Table"])
def test_charts_without_interactions(chart_type: str) -> None:
    assert chart_type in CHART_TYPES
    assert default_interactions(chart_type, has_color=True) is None


async def test_show_chart_keeps_the_chart_and_answers_with_its_id() -> None:
    session = ChartSession()
    result = stored()
    session.add_result(result)
    validator = FakeValidator(ValidationReport(warnings=("labels overlap",)))
    receipt = await show_chart(
        session,
        result_id=result.result_id,
        chart_type="Line Chart",
        encodings=LINES,
        title="Revenue",
        validator=validator,
    )
    assert receipt.ok
    assert receipt.chart_id is not None
    chart = session.chart(receipt.chart_id)
    assert chart is not None
    assert chart.result_id == result.result_id
    sent: Any = validator.inputs[0]
    assert orjson.loads(chart.rows) == orjson.loads(orjson.dumps(sent["data"]["values"]))
    assert receipt.to_dict() == {
        "ok": True,
        "chart_id": receipt.chart_id,
        "rows_drawn": 6,
        "chart": {**sent, "data": {"url": f"/flint/charts/{receipt.chart_id}/rows"}},
        "warnings": ["labels overlap"],
    }


async def test_the_rows_url_follows_where_the_routes_are_mounted() -> None:
    session = ChartSession()
    result = stored()
    session.add_result(result)
    receipt = await show_chart(
        session,
        result_id=result.result_id,
        chart_type="Line Chart",
        encodings=LINES,
        title="Revenue",
        url_prefix="/api/charts/",
    )
    assert receipt.chart is not None
    assert receipt.chart["data"] == {"url": f"/api/charts/charts/{receipt.chart_id}/rows"}
    assert chart_rows_url("c_1") == "/flint/charts/c_1/rows"


async def test_show_chart_without_a_validator_skips_it() -> None:
    session = ChartSession()
    result = stored()
    session.add_result(result)
    receipt = await show_chart(
        session,
        result_id=result.result_id,
        chart_type="Table",
        encodings={"x": "region"},
        title="t",
    )
    assert receipt.ok


async def test_a_chart_flint_rejects_is_not_kept() -> None:
    session = ChartSession()
    result = stored()
    session.add_result(result)
    receipt = await show_chart(
        session,
        result_id=result.result_id,
        chart_type="Line Chart",
        encodings=LINES,
        title="Revenue",
        validator=FakeValidator(ValidationReport(errors=("no rows",))),
    )
    assert receipt.to_dict() == {"ok": False, "problems": ["no rows"]}


async def test_an_unknown_result_asks_for_the_query_again() -> None:
    receipt = await show_chart(
        ChartSession(), result_id="r_gone", chart_type="Line Chart", encodings=LINES, title="t"
    )
    assert not receipt.ok
    assert receipt.problems == ("there is no result 'r_gone'; run the query again",)
