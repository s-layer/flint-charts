# How fields map to Flint types

Flint draws a field according to its semantic type: currency gets a currency format, a count
gets integer ticks and a zero baseline, a month gets a point on a timeline. `map_field` picks
that type from the field's S-LAYER `s_layer` block, so the chart follows what the semantic view
declares instead of what a model guesses.

| `value.kind` (and condition) | Flint type | Annotation |
| --- | --- | --- |
| `currency`, additive or semi-additive, or additivity unstated | `Amount` | `unit` = ISO code |
| `currency`, non-additive (unit price, average order value) | `Price` | `unit` = ISO code |
| `count` | `Count` | |
| `number` | `Number` | `unit` when the block sets one |
| `percentage` | `Percentage`, or `PercentageChange` once values leave `[0, 1]` | `intrinsicDomain` `[0, 1]`, widened to the values; values sent as fractions |
| `duration` | `Duration` | `unit`: `ms`, `seconds`, `minutes`, `hours` or `days` |
| `bytes`, `quantity` | `Quantity` | `unit` |
| `score` | `Score` | `intrinsicDomain` from the block's `range` |
| `category` | `Category` | `sortOrder` when the block orders it |
| `boolean` | `Boolean` | |
| `geo` | `Country`, `Region`, `State`, `City`, `ZipCode`, `Latitude` or `Longitude` by `level` | |
| `date` or `datetime`, grain `year` / `quarter` / `month` | `Year` / `YearQuarter` / `YearMonth` | |
| `date` or `datetime`, grain `week` or `day`; `date` with no grain or any sub-day grain | `Date` | |
| `datetime`, grain `hour` or finer, or no grain | `DateTime` | |
| `identifier` | `ID` | |

A few rules sit behind the table:

- **The query's grain wins.** When a query re-buckets a day-grain field by month, the result
  column holds months, so pass `grain="month"` and the column maps to `YearMonth`.
- **Timelines, never cycles.** Flint's `Month`, `Quarter`, `Week`, `Day` and `Hour` are cycles
  (January to December), so a monthly series is `YearMonth`. A week is drawn as the date of its
  Monday, because Flint's `YearWeek` wants `"2024-W01"` labels and treats them as a sequence of
  labels rather than a time axis.
- **Additivity decides Amount or Price.** The block's `aggregation.additivity` wins; when the
  block says nothing, pass the additivity the semantic definition declares.
- **A field without a block falls back to its Arrow type**: dates to `Date`, timestamps to
  `DateTime`, an integer `count` metric to `Count`, other numbers to `Number`, flags to
  `Boolean` and everything else to `Category`. The result has `fallback=True`, so a check can
  flag the missing block.

Each `FieldType` also has a `value_form`, which says how the column's values must be written
into the chart's rows for that type: a year as an integer, a quarter as `"2024-Q1"`, a month as
`"2024-01"`, a 0-100 percentage divided by 100.

Percentages carry `intrinsicDomain` `[0, 1]`, because Flint only formats a percentage as one
when a domain is set. On a color or size channel, Flint also clamps to that domain and pivots a
diverging scale on its centre, 50%. That suits shares and rates, but not growth or a change in
margin, which can leave the range. So once the values are known, `fit_to_values(field, low,
high)` turns a percentage outside `[0, 1]` into Flint's `PercentageChange`, with a domain wide
enough to hold the values. It pivots on zero when the values cross it and stays sequential when
they don't.

One limit remains in Flint itself: it guesses fractions against 0-100 from the data, and treats
the column as 0-100 when fewer than 80% of the values are within ±1. A change column that is
mostly above +100% is therefore formatted as plain numbers.

Display hints in the block (`decimals`, `compact`, `negative`, boolean labels) have no Flint
annotation to go to, so they are not passed on.

```python
import pyarrow as pa
from s_layer_flint_charts import field_display_names, map_field, semantic_types
from s_layer_semantic_formats import SLayerBlock

fields = {
    "revenue": map_field(
        SLayerBlock.model_validate({"value": {"kind": "currency", "currency": "EUR"}}),
        pa.decimal128(18, 2),
        label="Revenue",
    ),
    "ordered_at__month": map_field(
        SLayerBlock.model_validate({"value": {"kind": "date"}, "time": {"grain": "day"}}),
        pa.date32(),
        grain="month",
    ),
}
semantic_types(fields)
# {"revenue": {"semanticType": "Amount", "unit": "EUR"}, "ordered_at__month": "YearMonth"}
field_display_names(fields)
# {"revenue": "Revenue"}
```

The mapping is written against flint-chart `FLINT_VERSION`. The TypeScript package's tests
check every type it can emit against that release's own registry.
