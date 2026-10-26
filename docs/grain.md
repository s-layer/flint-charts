# Rows and the grain guard

The warehouse aggregates and a Flint chart draws one mark per row. Two steps sit between a
query result and the chart: `chart_rows` writes the result as JSON rows Flint reads correctly,
and `check_grain` refuses a chart that would merge rows, in words a model can act on.

## Writing the rows

`chart_rows(table, fields)` takes the pyarrow result and the `FieldType` of each column from
`map_field`, and returns `ChartRows`:

- Each column is written in its field's value form: a year as `2024`, a quarter as `"2024-Q1"`,
  a month as `"2024-01"`, a day or week as `"2024-01-15"`, a timestamp as ISO 8601. A zoned
  timestamp is bucketed by its local date, so a Tokyo order on 1 February counts in February.
- A 0-100 percentage is divided by 100. Flint guesses whether percentages run 0-1 or 0-100 from
  the data, so they always go out as fractions.
- Decimals with a fraction become floats. Whole-number decimals (an id, a `HUGEINT` sum) are
  integers. An integer outside ±(2^53 − 1), which a JavaScript number cannot hold exactly,
  makes its column strings rather than numbers that silently change.
- Nanosecond timestamps are cut to microseconds, the finest a Python or JavaScript date holds.
- Binary, duration and nested columns raise `UnsupportedColumnError`, and two columns with the
  same name raise `DuplicateColumnError`.
- Results longer than the cap (5,000 rows by default) are cut, and `capped` is set. A capped
  result should be filtered or aggregated further rather than charted.
- `fields` comes back fitted to the values: a percentage that leaves `[0, 1]` becomes
  `PercentageChange` (see [the mapping](mapping.md)).

`ChartRows.to_json()` gives the bytes to send, the same for the validator and the browser.

## Checking the grain

`check_grain(rows, request, metrics)` takes the rows, the model's `ChartRequest` (chart type,
encodings, chart properties) and a `Metric` for each metric column with its additivity. Every
other column is a dimension. It returns a `GrainCheck` whose `problems` say what is wrong; the
chart is safe to draw when there are none.

| Rule | Refused example | What the model is told |
| --- | --- | --- |
| The result has rows | an empty result | the query returned no rows, so there is nothing to chart |
| Every encoded column is in the rows, and no encoding sets `aggregate` | `y: {field: revenue, aggregate: sum}` | the query already aggregates, so charts draw one mark per row |
| Every dimension is on a channel or has one value per mark | monthly revenue by region drawn as one line with region on no channel | region has 2 values per month but is not on any channel; put it on a channel (such as color) or filter it to one value |
| No two rows share every placed value | monthly rows drawn on a quarter axis | 3 rows share one quarter and region mark; the result is finer than the chart, so query at the grain the chart shows |
| A stacked chart only stacks what adds up across its color | margin (a ratio) as bars stacked by region | a Bar Chart sums margin across region, but it does not add up; use a Line Chart or a Grouped Bar Chart, or take color off |
| | an account balance stacked by snapshot day | it cannot be summed over day |

Scatter plots, distribution charts (box, violin, strip, histogram, density) and tables draw
every row as its own mark or summarise many rows on purpose, so they skip the two
one-row-per-mark rules.

Stacking charts are bars, stacked bars, areas and streamgraphs whenever more than one color shares a bar or
point, and pie and donut charts always. Bars colored by the same column as their x axis do not
stack. A metric whose additivity is unknown is not stacked, since its sum may be wrong. Setting
`chartProperties.stackMode` to `"layered"` turns stacking off, except for streamgraphs, which
always stack.

A dimension that takes one value per mark, such as a region beside a country, is fine to leave
off the chart. Tooltip and text channels label a mark without drawing a new one, so a dimension
that is only in the tooltip still needs one value per mark. Only the measure is stacked (`x` or
`y`, or `size` for a pie), so a ratio in a tooltip does not stop revenue stacking.

## Stacked areas with gaps

Flint fills a missing point in a stacked area or streamgraph by interpolating between its
neighbours, which draws sales in a month that had none. When a stacked area is missing points:

- For additive metrics, `check_grain` adds the missing points (each facet, x value and color)
  as zeros. Other dimensions on the added rows are copied from a row with the same x, color or
  facet value. `GrainCheck.rows` is what to draw.
- Otherwise, or when another dimension has no single source for its value, it sets
  `stackMode` to `"layered"` in `GrainCheck.chart_properties`, so each area is drawn on its
  own. A streamgraph is always stacked, so it is refused instead.
- When the filled grid would pass the row cap, the chart is refused.

## Checked against Flint

The test suite builds Flint inputs from small results with both functions and runs them through
Flint's own `validateChart`: every chart the guard passes assembles with no errors and without
Flint aggregating rows, and the chart it refuses is one where Flint would have merged rows.
