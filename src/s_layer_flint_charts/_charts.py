"""
Assemble a Flint chart from a stored result and the model's chart choice.

The model names a result, a chart type, a column per channel and the words. Everything else
comes from the result: the rows, each column's semantic type and label, the source line and the
default interactions. A chart that would merge rows, or that Flint itself rejects, comes back as
plain-word problems instead of a chart.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, cast

import orjson

from s_layer_flint_charts._grain import ChartRequest, check_grain
from s_layer_flint_charts._mapping import field_display_names, percent_points, semantic_types
from s_layer_flint_charts._store import StoredChart

if TYPE_CHECKING:
    from collections.abc import Mapping

    from s_layer_flint_charts._store import ChartSession, StoredResult

__all__ = [
    "CHART_TYPES",
    "ChartReceipt",
    "ChartValidator",
    "ValidationReport",
    "chart_rows_url",
    "assemble_chart",
    "default_interactions",
    "show_chart",
]

CHART_TYPES: frozenset[str] = frozenset(
    {
        "Area Chart",
        "Bar Chart",
        "Choropleth",
        "Donut Chart",
        "Grouped Bar Chart",
        "Heatmap",
        "KPI Card",
        "Line Chart",
        "Lollipop Chart",
        "Pie Chart",
        "Scatter Plot",
        "Slope Chart",
        "Stacked Bar Chart",
        "Streamgraph",
        "Table",
    }
)
"""
The Flint chart types :func:`show_chart` draws, as Flint's Vega-Lite backend names them.

Semantic views return aggregated rows, so the charts that summarise raw rows (histograms, box
and density plots) are left out. A bubble chart is a ``Scatter Plot`` with ``size``. CI checks
every name against Flint's registry.
"""

_INDEX_CHARTS = frozenset({"Line Chart", "Area Chart", "Streamgraph", "Slope Chart"})
_ELEMENT_CHARTS = frozenset(
    {
        "Bar Chart",
        "Grouped Bar Chart",
        "Stacked Bar Chart",
        "Lollipop Chart",
        "Pie Chart",
        "Donut Chart",
    }
)
_INSPECT_CHARTS = frozenset({"Heatmap", "Scatter Plot", "Choropleth"})


def default_interactions(chart_type: str, *, has_color: bool) -> dict[str, object] | None:
    """
    The ``interaction_spec`` a chart type gets: hover readouts, and a legend toggle with color.

    Returns ``None`` for charts with nothing to interact with (KPI cards, tables).
    """
    presets: list[str]
    if chart_type in _INDEX_CHARTS:
        presets = ["inspect-index"]
    elif chart_type in _ELEMENT_CHARTS:
        presets = ["click-highlight"]
    elif chart_type in _INSPECT_CHARTS:
        presets = ["inspect"]
    else:
        return None
    if has_color and chart_type not in _INSPECT_CHARTS:
        presets.append("legend-toggle")
    return {"interactions": [{"type": preset} for preset in presets]}


@dataclass(frozen=True, kw_only=True)
class ValidationReport:
    """
    What Flint said about an assembled chart.

    ``errors`` stop the chart; ``warnings`` are passed on to the model. An implicit-aggregate
    warning counts as an error, since the grain guard should have stopped it.
    """

    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def valid(self) -> bool:
        """Whether Flint can draw the chart."""
        return not self.errors


class ChartValidator(Protocol):
    """Checks an assembled Flint input, such as :class:`FlintSidecar` does with Flint itself."""

    async def validate(self, flint_input: Mapping[str, object]) -> ValidationReport:
        """Validate one Flint ``ChartAssemblyInput``."""
        ...


@dataclass(frozen=True, kw_only=True)
class ChartReceipt:
    """
    What :func:`show_chart` answers: the chart to draw, or why there is none.

    ``chart`` is the Flint ``ChartAssemblyInput`` with ``data.url`` in place of the rows, so
    the model never reads them; the browser's chart component fetches the rows from that URL
    and puts them in ``data.values`` before handing the input to Flint.
    """

    chart_id: str | None
    chart: dict[str, object] | None = None
    problems: tuple[str, ...] = ()
    rows_drawn: int = 0
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        """Whether a chart was made."""
        return self.chart_id is not None

    def to_dict(self) -> dict[str, object]:
        """The receipt as a tool result, with only the keys that say something."""
        if not self.ok:
            return {"ok": False, "problems": list(self.problems)}
        receipt: dict[str, object] = {
            "ok": True,
            "chart_id": self.chart_id,
            "rows_drawn": self.rows_drawn,
            "chart": self.chart,
        }
        if self.warnings:
            receipt["warnings"] = list(self.warnings)
        return receipt


def chart_rows_url(chart_id: str, *, prefix: str = "/flint") -> str:
    """Where the browser fetches a chart's rows: the chart route, mounted at ``prefix``."""
    return f"{prefix.rstrip('/')}/charts/{chart_id}/rows"


def assemble_chart(
    result: StoredResult,
    *,
    chart_type: str,
    encodings: Mapping[str, str],
    title: str,
    subtitle: str | None = None,
    chart_properties: Mapping[str, object] | None = None,
    theme: str | Mapping[str, object] | None = None,
) -> tuple[dict[str, object] | None, tuple[str, ...]]:
    """
    Build the Flint ``ChartAssemblyInput`` for a stored result, or say why it cannot be drawn.

    Args:
        result: The stored query result.
        chart_type: One of :data:`CHART_TYPES`.
        encodings: A result column per Flint channel (``{"x": "month", "y": "revenue"}``).
        title: What the chart says, in words.
        subtitle: A second line, if any.
        chart_properties: Flint chart properties, such as ``{"stackMode": "layered"}``.
        theme: A Flint theme preset name or ``ThemeSpec``, from the app's settings.

    Returns:
        The Flint input and no problems, or ``None`` and the problems in plain words.
    """
    problems: list[str] = []
    if chart_type not in CHART_TYPES:
        problems.append(
            f"{chart_type!r} is not a chart type here; use one of {', '.join(sorted(CHART_TYPES))}"
        )
    if result.rows.capped:
        problems.append(
            f"the result has more than {len(result.rows.rows)} rows and was cut, so a chart of "
            "it would be wrong; filter it or use a coarser grain"
        )
    if not encodings:
        problems.append("put at least one column on a channel, such as x or y")
    if problems:
        return None, tuple(problems)

    check = check_grain(
        result.rows.rows,
        ChartRequest(
            chart_type=chart_type,
            encodings=encodings,
            chart_properties=dict(chart_properties or {}),
        ),
        result.metrics,
        cap=result.cap,
    )
    if not check.ok:
        return None, check.problems

    # The types fitted to the values (a percentage past [0, 1] is a PercentageChange), and
    # percentages Flint would misread as points sent as points.
    values, fields, _ = percent_points(check.rows, result.rows.fields)
    chart_spec: dict[str, object] = {
        "chartType": chart_type,
        "title": title,
        "encodings": {channel: {"field": column} for channel, column in encodings.items()},
        "source": f"{result.view}, queried {result.queried_at:%Y-%m-%d %H:%M} UTC",
    }
    if subtitle:
        chart_spec["subtitle"] = subtitle
    if check.chart_properties:
        chart_spec["chartProperties"] = check.chart_properties
    flint_input: dict[str, object] = {
        "data": {"values": values},
        "semantic_types": semantic_types(fields),
        "field_display_names": field_display_names(fields),
        "chart_spec": chart_spec,
    }
    interactions = default_interactions(chart_type, has_color="color" in encodings)
    if interactions is not None:
        flint_input["interaction_spec"] = interactions
    if theme is not None:
        flint_input["theme_spec"] = theme if isinstance(theme, str) else dict(theme)
    return flint_input, ()


async def show_chart(
    session: ChartSession,
    *,
    result_id: str,
    chart_type: str,
    encodings: Mapping[str, str],
    title: str,
    subtitle: str | None = None,
    chart_properties: Mapping[str, object] | None = None,
    theme: str | Mapping[str, object] | None = None,
    validator: ChartValidator | None = None,
    url_prefix: str = "/flint",
) -> ChartReceipt:
    """
    Draw a stored result as a Flint chart, keeping its rows for the browser under a chart id.

    The chart is checked by :func:`check_grain` and then, when a ``validator`` is given, by
    Flint itself, so the model hears about a bad chart in the same tool call.

    Args:
        session: The conversation's session.
        result_id: The result to draw, from the query tool.
        chart_type: One of :data:`CHART_TYPES`.
        encodings: A result column per Flint channel.
        title: What the chart says, in words.
        subtitle: A second line, if any.
        chart_properties: Flint chart properties.
        theme: A Flint theme preset name or ``ThemeSpec``.
        validator: Checks the assembled input with Flint, such as :class:`FlintSidecar`.
        url_prefix: Where the app mounts :func:`~s_layer_flint_charts.server.chart_routes`.

    Returns:
        A :class:`ChartReceipt`.
    """
    result = session.result(result_id)
    if result is None:
        return ChartReceipt(
            chart_id=None,
            problems=(f"there is no result {result_id!r}; run the query again",),
        )
    flint_input, problems = assemble_chart(
        result,
        chart_type=chart_type,
        encodings=encodings,
        title=title,
        subtitle=subtitle,
        chart_properties=chart_properties,
        theme=theme,
    )
    if flint_input is None:
        return ChartReceipt(chart_id=None, problems=problems)
    warnings: tuple[str, ...] = ()
    if validator is not None:
        report = await validator.validate(flint_input)
        if not report.valid:
            return ChartReceipt(chart_id=None, problems=report.errors)
        warnings = report.warnings
    data = flint_input["data"]
    assert isinstance(data, dict)
    rows = cast("list[object]", data["values"])
    chart = StoredChart(
        chart_id=session.new_chart_id(), result_id=result_id, rows=orjson.dumps(rows)
    )
    session.add_chart(chart)
    return ChartReceipt(
        chart_id=chart.chart_id,
        chart={
            **flint_input,
            "data": {"url": chart_rows_url(chart.chart_id, prefix=url_prefix)},
        },
        rows_drawn=len(rows),
        warnings=warnings,
    )
