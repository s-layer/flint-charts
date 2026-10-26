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
    from collections.abc import Collection, Mapping, Sequence

    from s_layer_semantic_formats import Additivity

__all__ = [
    "PIE_CHART_TYPES",
    "ROW_MARK_CHART_TYPES",
    "STACKING_CHART_TYPES",
    "ChartRequest",
    "GrainCheck",
    "Metric",
    "check_grain",
]

STACKING_CHART_TYPES: frozenset[str] = frozenset(
    {"Bar Chart", "Stacked Bar Chart", "Area Chart", "Streamgraph"}
)
"""Charts that stack their measure across the color field (Vega-Lite stacks bars and areas)."""

PIE_CHART_TYPES: frozenset[str] = frozenset({"Pie Chart", "Donut Chart", "Doughnut Chart"})
"""Charts whose slices add up to a whole: the measure is summed across the color field."""

ROW_MARK_CHART_TYPES: frozenset[str] = frozenset(
    {
        "Scatter Plot",
        "Bubble Chart",
        "Strip Plot",
        "Boxplot",
        "Violin Plot",
        "Histogram",
        "Density Plot",
        "Density Contour",
        "ECDF Plot",
        "Ridgeline Plot",
        "Regression",
        "Marginal Plot",
        "Table",
    }
)
"""
Charts that draw every row as its own mark or summarise a distribution of rows.

Several rows per category is what these charts are for, so the guard does not ask for one row
per mark.
"""

# Stacked areas, which Flint fills between missing points by interpolation. Only the area chart
# can be layered instead; a streamgraph is always stacked.
_AREA_CHART_TYPES = frozenset({"Area Chart", "Streamgraph"})
_ALWAYS_STACKED_CHART_TYPES = frozenset({"Streamgraph"})
# Channels that describe a mark without drawing a separate one.
_LABEL_CHANNELS = frozenset({"tooltip", "text", "label", "href"})
# Channels whose value is summed when bars, areas or slices stack.
_STACKED_CHANNELS = frozenset({"x", "y"})
_PIE_STACKED_CHANNELS = frozenset({"size", "theta"})
# Channels that place a mark, so two colors on different values of them do not stack.
_FACET_CHANNELS = frozenset({"column", "row", "facet"})
_POSITION_CHANNELS = frozenset({"x", "y"}) | _FACET_CHANNELS


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

    0. The result has rows.
    1. Every encoded column is in the rows, and no encoding asks Flint to ``aggregate``.
    2. Every dimension is on a channel that draws separate marks, or has one value per mark.
       Charts in :data:`ROW_MARK_CHART_TYPES` (scatter plots, distributions, tables) skip this
       rule and the next, since each row is meant to be its own mark.
       Tooltip and text channels only label a mark. Otherwise several rows would share a mark.
    3. No two rows have the same value on every such channel, as happens when a date is drawn
       at a coarser grain than the query returned.
    4. A chart that stacks across its color field (bars, areas, pie and donut slices) only
       stacks a metric that adds up across it: additive, or semi-additive along a dimension
       other than its snapshot one. A metric with unknown additivity is not stacked. Only the
       measure is stacked: ``x`` or ``y``, or ``size`` or ``theta`` for a pie.
    5. A stacked area or streamgraph has a value for every point (facet, x and color). Missing
       points of an additive metric are added as zeros, with each other dimension taken from a
       row with the same x, color or facet; otherwise the areas are layered instead of stacked,
       since Flint would fill the gaps by interpolation. A streamgraph cannot be layered, so it
       is refused instead.

    Args:
        rows: The rows the chart would draw, from :func:`chart_rows`.
        request: The chart type, encodings and chart properties.
        metrics: The metric columns of the result.
        cap: The most rows a densified stacked area may grow to.

    Returns:
        The :class:`GrainCheck`.
    """
    chart_properties = dict(request.chart_properties)
    if not rows:
        return GrainCheck(
            problems=("the query returned no rows, so there is nothing to chart",),
            rows=[],
            chart_properties=chart_properties,
        )
    encoded, problems = _encoded_columns(request)
    columns = list(rows[0])
    problems += [
        f"{column} is not a column of the result"
        for column in dict.fromkeys(encoded.values())
        if column not in columns
    ]
    if problems:
        return GrainCheck(
            problems=tuple(problems), rows=list(map(dict, rows)), chart_properties=chart_properties
        )

    placed = _dimensions_on(encoded, metrics, exclude=_LABEL_CHANNELS)
    if request.chart_type not in ROW_MARK_CHART_TYPES:
        labelled = set(_dimensions_on(encoded, metrics, only=_LABEL_CHANNELS))
        problems += _unplaced_dimension_problems(rows, columns, placed, labelled, metrics)
        if not problems:
            problems += _shared_mark_problems(rows, placed)
    stacked_metrics = _stacked_metrics(request, encoded, metrics, chart_properties)
    color = encoded.get("color")
    if stacked_metrics and color is not None and _stacks(rows, encoded, metrics, request):
        problems += _stacking_problems(stacked_metrics, color, metrics, request.chart_type)
    out_rows = [dict(row) for row in rows]
    if not problems and request.chart_type in _AREA_CHART_TYPES and stacked_metrics and color:
        out_rows, chart_properties, densify_problems = _dense_stacked_area(
            out_rows, request.chart_type, encoded, stacked_metrics, metrics, chart_properties, cap
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


def _dimensions_on(
    encoded: Mapping[str, str],
    metrics: Mapping[str, Metric],
    *,
    only: frozenset[str] | None = None,
    exclude: frozenset[str] = frozenset(),
) -> list[str]:
    """The dimension columns encoded on the given channels, in encoding order."""
    return list(
        dict.fromkeys(
            column
            for channel, column in encoded.items()
            if column not in metrics
            and channel not in exclude
            and (only is None or channel in only)
        )
    )


def _unplaced_dimension_problems(
    rows: Sequence[Mapping[str, object]],
    columns: Sequence[str],
    placed: Sequence[str],
    labelled: Collection[str],
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
            where_now = "only labels the marks" if column in labelled else "is not on any channel"
            problems.append(
                f"{column} has {most} values{where} but {where_now}; "
                "put it on a channel (such as color) or filter it to one value"
            )
    return problems


def _shared_mark_problems(rows: Sequence[Mapping[str, object]], placed: Sequence[str]) -> list[str]:
    """Rows that repeat every placed value would be drawn on top of each other, or merged."""
    per_mark: dict[tuple[object, ...], int] = defaultdict(int)
    for row in rows:
        per_mark[tuple(_key(row.get(name)) for name in placed)] += 1
    most = max(per_mark.values())
    if most < 2:
        return []
    mark = f"one {' and '.join(placed)} mark" if placed else "the chart's one mark"
    return [
        f"{most} rows share {mark}; the result is finer than the chart (for example months "
        "drawn as quarters), so query at the grain the chart shows"
    ]


def _stacked_metrics(
    request: ChartRequest,
    encoded: Mapping[str, str],
    metrics: Mapping[str, Metric],
    chart_properties: Mapping[str, object],
) -> list[str]:
    chart_type = request.chart_type
    if chart_type in PIE_CHART_TYPES:
        channels = _PIE_STACKED_CHANNELS
    elif chart_type in STACKING_CHART_TYPES:
        if (
            chart_properties.get("stackMode") == "layered"
            and chart_type not in _ALWAYS_STACKED_CHART_TYPES
        ):
            return []
        channels = _STACKED_CHANNELS
    else:
        return []
    return list(
        dict.fromkeys(
            column
            for channel, column in encoded.items()
            if column in metrics and channel in channels
        )
    )


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
    # Bars and areas are placed by their position and facet; a color column also on x is one of
    # them, so it gives each bar one color.
    others = _dimensions_on(
        {channel: column for channel, column in encoded.items() if channel != "color"},
        metrics,
        only=_POSITION_CHANNELS,
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
    chart_type: str,
    encoded: Mapping[str, str],
    stacked: Sequence[str],
    metrics: Mapping[str, Metric],
    chart_properties: dict[str, object],
    cap: int,
) -> tuple[list[dict[str, object]], dict[str, object], list[str]]:
    # Each facet is its own stack, so a point is a facet, an x value and a color.
    keys = _dimensions_on(encoded, metrics, only=frozenset({"x", "color"}) | _FACET_CHANNELS)
    present = {tuple(_key(row.get(name)) for name in keys) for row in rows}
    distinct = [list(dict.fromkeys(_key(row.get(name)) for row in rows)) for name in keys]
    total = 1
    for values in distinct:
        total *= len(values)
    if total == len(present):
        return rows, chart_properties, []

    def layered(reason: str) -> tuple[list[dict[str, object]], dict[str, object], list[str]]:
        if chart_type in _ALWAYS_STACKED_CHART_TYPES:
            return (
                rows,
                chart_properties,
                [
                    f"a {chart_type} fills missing points by interpolation and cannot be "
                    f"layered, and {reason}"
                ],
            )
        return rows, {**chart_properties, "stackMode": "layered"}, []

    if any(metrics[column].additivity != "additive" for column in stacked):
        return layered(
            f"{' and '.join(stacked)} has gaps that are not zeros; use an Area Chart or a "
            "Line Chart"
        )
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
    sources: dict[str, tuple[str | None, dict[object, object]]] = {}
    for name in rows[0]:
        if name in keys or name in metrics:
            continue
        source = _source(rows, name, keys)
        if source is None:
            # A dimension that no single key decides has no known value at an added point.
            return layered(
                f"{name} has no known value at the missing points; filter it to one value or "
                "leave it out of the query"
            )
        sources[name] = source
    filled = list(rows)
    for combo in _product(distinct):
        if combo in present:
            continue
        point = dict(zip(keys, combo, strict=True))
        row: dict[str, object] = {}
        for name in rows[0]:
            if name in keys:
                row[name] = lookup[keys.index(name)][point[name]]
            elif name in metrics:
                row[name] = 0 if name in stacked else None
            else:
                key, values = sources[name]
                row[name] = values[None if key is None else point[key]]
        filled.append(row)
    return filled, chart_properties, []


def _source(
    rows: Sequence[Mapping[str, object]], name: str, keys: Sequence[str]
) -> tuple[str | None, dict[object, object]] | None:
    """
    How to fill a dimension at an added point: the key column that decides it and its values.

    A constant column is decided by no key: ``(None, {None: value})``. Returns ``None`` when no
    single key decides the column.
    """
    values = {_key(row.get(name)): row.get(name) for row in rows}
    if len(values) == 1:
        return None, {None: next(iter(values.values()))}
    for key in keys:
        by_key: dict[object, set[object]] = defaultdict(set)
        decided: dict[object, object] = {}
        for row in rows:
            by_key[_key(row.get(key))].add(_key(row.get(name)))
            decided[_key(row.get(key))] = row.get(name)
        if all(len(found) == 1 for found in by_key.values()):
            return key, decided
    return None


def _product(lists: Sequence[Sequence[object]]) -> list[tuple[object, ...]]:
    combos: list[tuple[object, ...]] = [()]
    for values in lists:
        combos = [(*combo, value) for combo in combos for value in values]
    return combos


def _key(value: object) -> object:
    """A hashable stand-in for a row value."""
    return value if isinstance(value, str | int | float | bool | None) else repr(value)
