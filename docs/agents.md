# Charts in an agent

An agent charts a semantic view in two tool calls. It queries the view and reads a summary of
the result, then asks for a chart of that result. The rows stay on your server the whole time:
the model sees only the summary, and the browser fetches the rows when it draws the chart.

```
model ──query_sales──▶ server runs the query, keeps the result ──▶ summary + result_id
model ──show_chart───▶ server assembles and checks the chart   ──▶ Flint input with data.url
browser ──GET data.url───────────────────────────────────────────▶ the chart's rows
```

Install the extras you need:

```bash
pip install 's-layer-flint-charts[pydantic-ai,server,validate]'
```

## The toolset

`chart_toolset` gives a Pydantic AI agent one `query_<view>` tool per semantic view and a
`show_chart` tool. The tools keep results and charts in a `ChartStore`, one session per
conversation, so tell the toolset which conversation a run belongs to:

```python
from dataclasses import dataclass

from pydantic_ai import Agent, RunContext
from s_layer_flint_charts import ChartStore, FlintSidecar
from s_layer_flint_charts.pydantic_ai import chart_toolset

from myapp.views import Orders, Sales


@dataclass
class Conversation:
    id: str


def conversation_id(ctx: RunContext[Conversation]) -> str:
    return ctx.deps.id


store = ChartStore()
sidecar = FlintSidecar()  # start it once, with `async with`, when the app starts
agent = Agent(
    "anthropic:claude-sonnet-4-6",
    deps_type=Conversation,
    toolsets=[
        chart_toolset([Sales, Orders], store=store, session_id=conversation_id, validator=sidecar)
    ],
)
```

Each query tool takes semolina's query spec: `metrics`, `dimensions` (with a grain such as
`ordered_at__month`), `where`, `order_by` and `limit`. Its schema lists the view's own field
names. It answers with the row count, and for each column its kind (metric or dimension),
Flint type, label, unit, range or distinct values, plus a few sample rows and a `result_id`. A
spec that names a field the view lacks goes back to the model to fix.

`show_chart` takes the `result_id`, a chart type, a result column per channel and a title. It
refuses a chart that would merge rows, a result cut at the row cap (5,000 rows by default), or a
chart Flint rejects, and those problems also go back to the model to fix. Otherwise it answers
with the assembled Flint input. That input carries the semantic types, labels, interactions and
the source line, but its `data` holds only a URL in place of the rows:

```json
{
  "ok": true,
  "chart_id": "c_1KZ…",
  "rows_drawn": 36,
  "chart": {
    "data": {"url": "/flint/charts/c_1KZ…/rows"},
    "semantic_types": {"revenue": {"semanticType": "Amount", "unit": "USD"}, "…": "…"},
    "chart_spec": {"chartType": "Line Chart", "title": "Revenue by month", "…": "…"},
    "interaction_spec": {"interactions": [{"type": "inspect-index"}]}
  }
}
```

The tool result costs the model a few hundred tokens per chart, whatever the row count.

## The rows route

Mount the route the `data.url` points at. `session_of` tells it which conversation a request
belongs to, so one conversation never reads another's charts:

```python
from starlette.applications import Starlette
from starlette.routing import Mount
from s_layer_flint_charts.server import chart_routes


def session_of(request) -> str | None:
    return request.session.get("conversation_id")  # however your app knows it


app = Starlette(routes=[Mount("/flint", routes=chart_routes(store, session_of))])
```

`GET /flint/charts/{chart_id}/rows` answers with the rows as a JSON array, compressed with zstd
or gzip as the browser accepts, and 404 for an unknown, expired or foreign chart. If you mount
the routes elsewhere, pass the same prefix as `url_prefix=` to `chart_toolset`.

The rows are kept per chart rather than per result, because a chart may draw different rows from
its result: the grain guard can add zeros to a stacked area, and a percentage may go out as
points.

## Drawing the chart

Flint does not fetch `data.url` itself. The chart component fetches it and puts the rows in
`data.values` before calling Flint:

```ts
const rows = await (await fetch(chart.data.url)).json();
const spec = assembleVegaLite({ ...chart, data: { values: rows } });
```

`@s-layer/flint-charts` will ship this as a component for CopilotKit and assistant-ui.

## Checking charts with Flint

`FlintSidecar` runs [`flint-chart-mcp`](https://www.npmjs.com/package/flint-chart-mcp), the
release this package is pinned to, and asks it to validate every chart as the Vega-Lite backend
would draw it. Flint errors stop the chart, and so does its `implicit-aggregate` warning, which
means Flint would merge rows. Other warnings are passed on to the model.

By default the sidecar starts with `npx`, so Node must be installed. To run it as a separate
service, start `flint-chart-mcp --transport http --disable-file-reference` and connect with
`FlintSidecar(url="http://flint:8080/mcp")`. Without a validator, charts are checked by the
grain guard alone.

## Limits

- A session holds its newest 20 results and 50 charts, and is forgotten an hour after its last
  use. A chart whose rows have expired can't be redrawn until the query runs again. Set these
  with `ChartStore(ttl=…, max_results=…, max_charts=…)`.
- The store is in memory, per process. Run one process, or route each conversation to the same
  one.

## See also

- [Rows and the grain guard](grain.md)
- [Mapping semantic formats to Flint](mapping.md)
