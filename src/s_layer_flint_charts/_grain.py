"""
Refuse a chart that would merge rows, before Flint sees it.

The warehouse aggregates and the chart draws one mark per row. When several rows land on one
mark, Flint and Vega-Lite add them up or average them without saying much, which is how a ratio,
a distinct count or a balance goes silently wrong. These checks run on the rows a chart is about
to draw and say in plain words what is wrong, so the model can fix its request.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from s_layer_flint_charts._rows import DEFAULT_ROW_CAP

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from s_layer_semantic_formats import Additivity

__all__ = [
    "PIE_CHART_TYPES",
    "STACKING_CHART_TYPES",
    "ChartRequest",
    "GrainCheck",
    "Metric",
    "check_grain",
]

STACKING_CHART_TYPES: frozenset[str] = frozenset({"Bar Chart", "Stacked Bar Chart", "Area Chart"})
"""Charts that stack their measure across the color field (Vega-Lite stacks bars and areas)."""

PIE_CHART_TYPES: frozenset[str] = frozenset({"Pie Chart", "Donut Chart"})
"""Charts whose slices add up to a whole: the measure is summed across the color field."""


@dataclass(frozen=True, kw_only=True)
class Metric:
    """
    What the grain guard needs to know about a metric column.

    ``additivity`` is the metric's additivity from its ``s_layer`` block or its semantic
    definition, or ``None`` when neither says. ``non_additive_by`` names the result columns a
    semi-additive metric must not be summed over (its snapshot dimensions).
    """

    additivity: Additivity | None = None
    non_additive_by: frozenset[str] = frozenset()


@dataclass(frozen=True, kw_only=True)
class ChartRequest:
    """
    The model's chart choice: a Flint chart type, a column per channel and chart properties.

    An encoding is a column name, or a Flint encoding object with a ``field``.
    """

    chart_type: str
    encodings: Mapping[str, str | Mapping[str, object]]
    chart_properties: Mapping[str, object] = field(default_factory=dict[str, object])


@dataclass(frozen=True, kw_only=True)
class GrainCheck:
    """
    The guard's verdict.

    ``problems`` are plain-word reasons to refuse the chart; it is safe to draw only when there
    are none. ``rows`` and ``chart_properties`` are what to draw: for a stacked area they may
    have zeros added for missing points or ``stackMode`` set to ``"layered"``.
    """

    problems: tuple[str, ...]
    rows: list[dict[str, object]]
    chart_properties: dict[str, object]

    @property
    def ok(self) -> bool:
        """Whether the chart can be drawn."""
        return not self.problems


def check_grain(
    rows: Sequence[Mapping[str, object]],
    request: ChartRequest,
    metrics: Mapping[str, Metric],
    *,
    cap: int = DEFAULT_ROW_CAP,
) -> GrainCheck:
    """
    Check that a chart draws exactly one mark per row and stacks only what adds up.

    Every result column not in ``metrics`` is a dimension. The rules:

    1. Every encoded column exists, and no encoding asks Flint to ``aggregate``.
    2. Every dimension is on a channel or has one value per mark. Otherwise several rows
       would share a mark.
    3. A chart that stacks across its color field (bars, areas, pie and donut slices) only
       stacks a metric that adds up across it: additive, or semi-additive along a dimension
       other than its snapshot one. A metric with unknown additivity is not stacked.
    4. A stacked area has a value for every point. Missing points of an additive metric are
       added as zeros; otherwise the areas are layered instead of stacked, since Flint would
       fill the gaps by interpolation.

    Args:
        rows: The rows the chart would draw, from :func:`chart_rows`.
        request: The chart type, encodings and chart properties.
        metrics: The metric columns of the result.
        cap: The most rows a densified stacked area may grow to.

    Returns:
        The :class:`GrainCheck`.
    """
    chart_properties = dict(request.chart_properties)
    encoded, problems = _encoded_columns(request)
    columns = list(rows[0]) if rows else []
    known = set(columns) | set(metrics)
    problems += [
        f"{column} is not a column of the result"
        for column in encoded.values()
        if column not in known
    ]
    if problems:
        return GrainCheck(
            problems=tuple(problems), rows=list(map(dict, rows)), chart_properties=chart_properties
        )

    placed = [column for column in dict.fromkeys(encoded.values()) if column not in metrics]
    problems += _unplaced_dimension_problems(rows, columns, placed, metrics)
    stacked_metrics = _stacked_metrics(request, encoded, metrics, chart_properties)
    color = encoded.get("color")
    if stacked_metrics and color is not None and _stacks(rows, encoded, metrics, request):
        problems += _stacking_problems(stacked_metrics, color, metrics, request.chart_type)
    out_rows = [dict(row) for row in rows]
    if not problems and request.chart_type == "Area Chart" and stacked_metrics and color:
        out_rows, chart_properties, densify_problems = _dense_stacked_area(
            out_rows, placed, stacked_metrics, metrics, chart_properties, cap
        )
        problems += densify_problems
    return GrainCheck(problems=tuple(problems), rows=out_rows, chart_properties=chart_properties)


def _encoded_columns(request: ChartRequest) -> tuple[dict[str, str], list[str]]:
    encoded: dict[str, str] = {}
    problems: list[str] = []
    for channel, encoding in request.encodings.items():
        if isinstance(encoding, str):
            encoded[channel] = encoding
            continue
        if "aggregate" in encoding:
            problems.append(
                f"the {channel} encoding asks the chart to aggregate; the query already "
                "aggregates, so charts draw one mark per row"
            )
        column = encoding.get("field")
        if isinstance(column, str):
            encoded[channel] = column
    return encoded, problems


def _unplaced_dimension_problems(
    rows: Sequence[Mapping[str, object]],
    columns: Sequence[str],
    placed: Sequence[str],
    metrics: Mapping[str, Metric],
) -> list[str]:
    problems: list[str] = []
    for column in columns:
        if column in metrics or column in placed:
            continue
        per_mark: dict[tuple[object, ...], set[object]] = defaultdict(set)
        for row in rows:
            per_mark[tuple(_key(row.get(name)) for name in placed)].add(_key(row.get(column)))
        most = max((len(values) for values in per_mark.values()), default=0)
        if most > 1:
            where = f" per {' and '.join(placed)}" if placed else ""
            problems.append(
                f"{column} has {most} values{where} but is not on any channel; "
                "put it on a channel (such as color) or filter it to one value"
            )
    return problems


def _stacked_metrics(
    request: ChartRequest,
    encoded: Mapping[str, str],
    metrics: Mapping[str, Metric],
    chart_properties: Mapping[str, object],
) -> list[str]:
    chart_type = request.chart_type
    if chart_type in PIE_CHART_TYPES:
        pass
    elif chart_type in STACKING_CHART_TYPES:
        if chart_properties.get("stackMode") == "layered":
            return []
    else:
        return []
    return [
        column for channel, column in encoded.items() if column in metrics and channel != "color"
    ]


def _stacks(
    rows: Sequence[Mapping[str, object]],
    encoded: Mapping[str, str],
    metrics: Mapping[str, Metric],
    request: ChartRequest,
) -> bool:
    """Whether more than one color shares a bar, an area point or a pie."""
    if request.chart_type in PIE_CHART_TYPES:
        return True
    color = encoded["color"]
    # The dimensions on the other channels pick the bar; a color column also on x is one of them.
    others = list(
        dict.fromkeys(
            column
            for channel, column in encoded.items()
            if channel != "color" and column not in metrics
        )
    )
    colors: dict[tuple[object, ...], set[object]] = defaultdict(set)
    for row in rows:
        colors[tuple(_key(row.get(name)) for name in others)].add(_key(row.get(color)))
    return any(len(values) > 1 for values in colors.values())


def _stacking_problems(
    stacked: Sequence[str], color: str, metrics: Mapping[str, Metric], chart_type: str
) -> list[str]:
    problems: list[str] = []
    for column in stacked:
        metric = metrics[column]
        match metric.additivity:
            case "additive":
                continue
            case "semi_additive" if color not in metric.non_additive_by:
                continue
            case "semi_additive":
                reason = f"it cannot be summed over {color}"
            case "non_additive":
                reason = "it does not add up (a ratio, average or distinct count)"
            case None:
                reason = "its additivity is not declared, so its sum may be wrong"
        problems.append(
            f"a {chart_type} sums {column} across {color}, but {reason}; "
            "use a Line Chart or a Grouped Bar Chart, or take color off"
        )
    return problems


def _dense_stacked_area(
    rows: list[dict[str, object]],
    placed: Sequence[str],
    stacked: Sequence[str],
    metrics: Mapping[str, Metric],
    chart_properties: dict[str, object],
    cap: int,
) -> tuple[list[dict[str, object]], dict[str, object], list[str]]:
    keys = list(placed)
    present = {tuple(_key(row.get(name)) for name in keys) for row in rows}
    distinct = [list(dict.fromkeys(_key(row.get(name)) for row in rows)) for name in keys]
    total = 1
    for values in distinct:
        total *= len(values)
    if total == len(present):
        return rows, chart_properties, []
    if any(metrics[column].additivity != "additive" for column in stacked):
        return rows, {**chart_properties, "stackMode": "layered"}, []
    if total > cap:
        return (
            rows,
            chart_properties,
            [
                f"filling the gaps in this stacked area would take {total} points, over the "
                f"{cap}-row cap; filter it or use a coarser grain"
            ],
        )
    lookup = [{_key(row.get(name)): row.get(name) for row in rows} for name in keys]
    # Unplaced dimensions have one value; other metrics have no value at an added point.
    filler = {name: None if name in metrics else value for name, value in rows[0].items()}
    filled = list(rows)
    for combo in _product(distinct):
        if combo in present:
            continue
        row = dict(filler)
        for name, value, values in zip(keys, combo, lookup, strict=True):
            row[name] = values[value]
        for column in stacked:
            row[column] = 0
        filled.append(row)
    return filled, chart_properties, []


def _product(lists: Sequence[Sequence[object]]) -> list[tuple[object, ...]]:
    combos: list[tuple[object, ...]] = [()]
    for values in lists:
        combos = [(*combo, value) for combo in combos for value in values]
    return combos


def _key(value: object) -> object:
    """A hashable stand-in for a row value."""
    return value if isinstance(value, str | int | float | bool | None) else repr(value)
