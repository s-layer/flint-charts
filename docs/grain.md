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
- Decimals become floats. An integer outside ±(2^53 − 1), which a JavaScript number cannot hold
  exactly, makes its column strings rather than numbers that silently change.
- Binary, duration and nested columns raise `UnsupportedColumnError`.
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
| Every encoded column exists, and no encoding sets `aggregate` | `y: {field: revenue, aggregate: sum}` | the query already aggregates, so charts draw one mark per row |
| Every dimension is on a channel or has one value per mark | monthly revenue by region drawn as one line with region on no channel | region has 2 values per month but is not on any channel; put it on a channel (such as color) or filter it to one value |
| A stacked chart only stacks what adds up across its color | margin (a ratio) as bars stacked by region | a Bar Chart sums margin across region, but it does not add up; use a Line Chart or a Grouped Bar Chart, or take color off |
| | an account balance stacked by snapshot day | it cannot be summed over day |

Stacking charts are bars, stacked bars and areas whenever more than one color shares a bar or
point, and pie and donut charts always. Bars colored by the same column as their x axis do not
stack. A metric whose additivity is unknown is not stacked, since its sum may be wrong. Setting
`chartProperties.stackMode` to `"layered"` turns stacking off.

A dimension that takes one value per mark, such as a region beside a country, is fine to leave
off the chart.

## Stacked areas with gaps

Flint fills a missing point in a stacked area by interpolating between its neighbours, which
draws sales in a month that had none. When a stacked area is missing points:

- For additive metrics, `check_grain` adds the missing points as zeros. `GrainCheck.rows` is
  what to draw.
- Otherwise it sets `stackMode` to `"layered"` in `GrainCheck.chart_properties`, so each area
  is drawn on its own.
- When the filled grid would pass the row cap, the chart is refused.

## Checked against Flint

The test suite builds Flint inputs from small results with both functions and runs them through
Flint's own `validateChart`: every chart the guard passes assembles with no errors and without
Flint aggregating rows, and the chart it refuses is one where Flint would have merged rows.
