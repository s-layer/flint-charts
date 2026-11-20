# Rows and the grain guard

The warehouse aggregates and a Flint chart draws one mark per row. Two steps sit between a query
result and the chart: {py:func}`chart_rows <s_layer_flint_charts.chart_rows>` writes the result as
JSON rows Flint reads correctly, and {py:func}`check_grain <s_layer_flint_charts.check_grain>`
refuses a chart that would merge rows, in words a model can act on.

## Writing the rows

`chart_rows(table, fields)` takes the pyarrow result and the
{py:class}`FieldType <s_layer_flint_charts.FieldType>` of each column from
{py:func}`map_field <s_layer_flint_charts.map_field>`, and returns
{py:class}`ChartRows <s_layer_flint_charts.ChartRows>`:

- Each column is written in its field's value form: a year as `2024`, a quarter as `"2024-Q1"`,
  a month as `"2024-01"`, a day or week as `"2024-01-15"`, a timestamp as ISO 8601. A zoned
  timestamp is bucketed by its local date, so a Tokyo order on 1 February counts in February.
- A 0-100 percentage is divided by 100, so every percentage is held as a fraction, and its
  Flint annotation says so (see [the mapping](mapping.md)).
- Decimals with a fraction become floats. Whole-number decimals (an id, a `HUGEINT` sum) are
  integers. An integer outside ±(2^53 − 1), which a JavaScript number cannot hold exactly,
  makes its column strings, so no value silently changes.
- Nanosecond timestamps are cut to microseconds, the finest a Python or JavaScript date holds.
- Binary, duration and nested columns raise
  {py:exc}`UnsupportedColumnError <s_layer_flint_charts.UnsupportedColumnError>`, and two columns
  with the same name raise
  {py:exc}`DuplicateColumnError <s_layer_flint_charts.DuplicateColumnError>`.
- Results longer than the cap (5,000 rows by default) are cut, and
  {py:attr}`capped <s_layer_flint_charts.ChartRows.capped>` is set. Filter or aggregate a capped
  result further instead of charting it.
- `fields` comes back fitted to the values: a percentage that leaves `[0, 1]` becomes
  `PercentageChange` (see [the mapping](mapping.md)).

{py:meth}`ChartRows.to_json() <s_layer_flint_charts.ChartRows.to_json>` gives the bytes to send, the
same for the validator and the browser.

## Checking the grain

`check_grain(rows, request, metrics)` takes the rows, the model's
{py:class}`ChartRequest <s_layer_flint_charts.ChartRequest>` (chart type, encodings, chart
properties) and a {py:class}`Metric <s_layer_flint_charts.Metric>` for each metric column with its
additivity. Every other column is a dimension. It returns a
{py:class}`GrainCheck <s_layer_flint_charts.GrainCheck>` whose `problems` say what is wrong; the
chart is safe to draw when there are none.

| Rule | Refused example | What the model is told |
| --- | --- | --- |
| The result has rows | an empty result | the query returned no rows, so there is nothing to chart |
| Every encoded column is in the rows, and no encoding sets `aggregate` | `y: {field: revenue, aggregate: sum}` | the query already aggregates, so charts draw one mark per row |
| Every dimension is on a channel or has one value per mark | monthly revenue by region drawn as one line with region on no channel | region has 2 values per month but is not on any channel; put it on a channel (such as color) or filter it to one value |
| No two rows share every placed value | monthly rows drawn on a quarter axis | 3 rows share one quarter and region mark; the result is finer than the chart, so query at the grain the chart shows |
| A stacked chart only stacks what adds up across its color | margin (a ratio) as bars stacked by region | a Bar Chart sums margin across region, but it does not add up; use a Line Chart or a Grouped Bar Chart, or take color off |
| | an account balance stacked by snapshot day | it cannot be summed over day |
| | revenue stacked by region, when revenue's block declares no additivity | a Bar Chart sums revenue across region, but its additivity is not declared, so its sum may be wrong; use a Line Chart or a Grouped Bar Chart, or take color off |

These refusals come earlier, from
{py:func}`show_chart <s_layer_flint_charts.show_chart>` (the function the toolset's `show_chart`
tool calls), before the grain guard runs:

| Refused | What the model is told |
| --- | --- |
| a chart type outside {py:data}`CHART_TYPES <s_layer_flint_charts.CHART_TYPES>`, such as `Funnel` | 'Funnel' is not a chart type here; use one of Area Chart, Bar Chart, … |
| no encodings | put at least one column on a channel, such as x or y |
| a result cut at the row cap | the result has more than 5000 rows and was cut, so a chart of it would be wrong; filter it or use a coarser grain |
| a `result_id` the conversation no longer holds: expired, pushed out by newer results, or never its own | there is no result 'r_…'; run the query again |

Scatter plots, distribution charts (box, violin, strip, histogram, density) and tables draw
every row as its own mark or summarise many rows on purpose, so they skip the two
one-row-per-mark rules.

Stacking charts are bars, stacked bars, areas and streamgraphs whenever more than one color shares a
bar or point, and pie and donut charts always. Bars colored by the same column as their x axis do
not stack. A stacking chart of a metric whose additivity is not declared is refused, since its
sum may be wrong. Setting `chartProperties.stackMode` to `"layered"` turns stacking off, except for
streamgraphs, which always stack.

A dimension that takes one value per mark, such as a region beside a country, is fine to leave
off the chart. Tooltip and text channels label a mark without drawing a new one, so a dimension
that is only in the tooltip still needs one value per mark. Only the measure is stacked (`x` or
`y`, or `size` or `theta` for a pie), so a ratio in a tooltip does not stop revenue stacking.

### Where additivity comes from

`check_grain` takes each metric's additivity from the `Metric` you pass it. Under
{py:func}`chart_toolset <s_layer_flint_charts.pydantic_ai.chart_toolset>`, the toolset makes each
`Metric` from the field's `s_layer` block (semolina's `semantic_format=`) and nothing else:

- If the block declares `aggregation.additivity`, that is the metric's additivity.
- If not, a `percentage` or `score` value is non-additive.
- Any other metric has none.

So a currency, count or number metric whose block doesn't declare additivity, and any metric
with no block at all, can't be stacked by color: the chart is refused with "its additivity is
not declared". Declare `additive` on each metric you want stacked:

```python
from semolina import Dimension, Metric, SemanticView


class Sales(SemanticView, view="analytics.sales"):
    revenue = Metric[float](
        label="Revenue",
        semantic_format={
            "value": {"kind": "currency", "currency": "USD"},
            "aggregation": {"additivity": "additive"},
        },
    )
    region = Dimension[str](label="Region", semantic_format={"value": {"kind": "category"}})
```

Declare a snapshot metric, such as an account balance, `semi_additive`, and name its snapshot
dimensions in `aggregation.by`, such as `"by": ["snapshot_date"]`. It then stacks across any
other dimension.

## Stacked areas with gaps

Flint fills a missing point in a stacked area or streamgraph by interpolating between its
neighbours, which draws sales in a month that had none. When a stacked area is missing points:

- For additive metrics, `check_grain` adds the missing points (each facet, x value and color)
  as zeros. Other dimensions on the added rows are copied from a row with the same x, color or
  facet value. {py:attr}`GrainCheck.rows <s_layer_flint_charts.GrainCheck.rows>` is what to draw.
- Otherwise, or when another dimension has no single source for its value, it sets `stackMode` to
  `"layered"` in
  {py:attr}`GrainCheck.chart_properties <s_layer_flint_charts.GrainCheck.chart_properties>`, so each
  area is drawn on its own. A streamgraph is always stacked, so it is refused instead.
- When the filled grid would pass the row cap, the chart is refused.

## Checked against Flint

The test suite builds Flint inputs from small results with both functions and runs them through
Flint's own `validateChart`: every chart the guard passes assembles with no errors and without
Flint aggregating rows, and the chart it refuses is one where Flint would have merged rows.
