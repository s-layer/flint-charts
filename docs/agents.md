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
pip install 's-layer-flint-charts[pydantic-ai,server]'
```

## The toolset

{py:func}`chart_toolset <s_layer_flint_charts.pydantic_ai.chart_toolset>` gives a Pydantic AI agent
one `query_<view>` tool per semantic view and a `show_chart` tool. The tools keep results and charts
in a {py:class}`ChartStore <s_layer_flint_charts.ChartStore>`, one session per conversation, so tell
the toolset which conversation a run belongs to:

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
sidecar = FlintSidecar()  # started once by the app's lifespan, below
agent = Agent(
    "anthropic:claude-sonnet-4-6",
    deps_type=Conversation,
    toolsets=[
        chart_toolset([Sales, Orders], store=store, session_id=conversation_id, validator=sidecar)
    ],
)
```

The toolset needs semolina 0.10.0 or later. Each query tool runs its query with semolina's
`query.aexecute()`, so it needs an async engine registered under `"default"`, the name a query
looks up when it names no other. A sync engine isn't enough: semolina looks async engines up in
a registry of their own. `create_async_engine(..., register=True)` creates and registers one in
one call (install `semolina[async]` for it), and the lifespan under
[Checking charts with Flint](#checking-charts-with-flint) shows where it goes. To run queries
some other way, pass `fetch=` to
{py:func}`chart_toolset <s_layer_flint_charts.pydantic_ai.chart_toolset>`: an async function
that takes the semolina `Query` and returns a pyarrow `Table`.

Each query tool's description tells the model which view the tool queries and what the view
holds. It comes from the view class's `description=`, which semolina codegen writes from the
warehouse's view comment. A view with no `description=`, or a blank one, falls back to its class
docstring. `description=` is a keyword of the class statement:

```python
from semolina import Dimension, Metric, SemanticView


class Sales(
    SemanticView,
    view="analytics.sales",
    description="Booked orders and revenue, by region and order date",
):
    revenue = Metric[float](label="Revenue")
    region = Dimension[str](label="Region")
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

Mount the route the `data.url` points at with
{py:func}`chart_routes <s_layer_flint_charts.server.chart_routes>`. `session_of` tells it which
conversation a request belongs to, so one conversation never reads another's charts:

```python
import os

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.routing import Mount
from s_layer_flint_charts.server import chart_routes


def session_of(request) -> str | None:
    return request.session.get("conversation_id")  # however your app knows it


app = Starlette(
    routes=[Mount("/flint", routes=chart_routes(store, session_of))],
    middleware=[Middleware(SessionMiddleware, secret_key=os.environ["SESSION_SECRET"])],
)
```

`GET /flint/charts/{chart_id}/rows` answers with the rows as a JSON array, compressed with zstd
or gzip as the browser accepts, and 404 for an unknown, expired or foreign chart.

`session_of(request)` must return the same id that your `session_id` function gave the agent
run for that conversation. The run stored its charts in that session, so the route answers 404
for any other id, or for `None`. `session_of` may also be async.

The example reads `request.session`, which needs Starlette's `SessionMiddleware` on the app (it
signs the cookie, and needs the `itsdangerous` package). Your app still has to write
`conversation_id` into the session when a conversation starts, as the same id its agent runs use.

`data.url` is `url_prefix` followed by `/charts/{chart_id}/rows`, and `url_prefix` defaults to
`/flint`. If you mount the routes elsewhere, pass the full path from the origin as `url_prefix=`
to {py:func}`chart_toolset <s_layer_flint_charts.pydantic_ai.chart_toolset>`, including any outer
mount. For routes at `/flint` in an app you mount at `/api`, pass `url_prefix="/api/flint"`.

The rows are kept per chart, not per result, because a chart may draw different rows from
its result: the grain guard can add zeros to a stacked area.

## Drawing the chart

Flint does not fetch `data.url` itself, so the browser fetches the rows and puts them in
`data.values` before Flint draws the chart. The npm package `@s-layer/flint-charts` does this
for CopilotKit, assistant-ui and plain React; see [Charts in a chat UI](chat-ui.md).

## Checking charts with Flint

{py:class}`FlintSidecar <s_layer_flint_charts.FlintSidecar>` runs a small Node script that ships
with this package and calls Flint's own `validateChart` on every chart, as the Vega-Lite backend
would draw it, with the `flint-chart` release this package is pinned to. The two talk in JSON lines
over stdin and stdout. Flint errors stop the chart, and so does its `implicit-aggregate` warning,
which means Flint would merge rows. Other warnings are passed on to the model.

The sidecar needs Node 18 or later where the Python app runs. The package is pinned to
`flint-chart` 1.1.0, the value of
{py:data}`FLINT_VERSION <s_layer_flint_charts.FLINT_VERSION>`. By default the sidecar starts
with `npx`, which downloads that release the first time.

Start the sidecar once, when the app starts, and share it. It's an async context manager:
entering it starts Node, and leaving it shuts Node down. A Starlette lifespan does both, and is also
the place to register the async engine the query tools run on:

```python
from contextlib import asynccontextmanager

from semolina import create_async_engine
from starlette.applications import Starlette

# with the imports, store, sidecar and session_of from the examples above


@asynccontextmanager
async def lifespan(app: Starlette):
    # the engine reads [connections.default] from .semolina.toml
    async with create_async_engine("default", register=True), sidecar:
        yield


app = Starlette(
    routes=[Mount("/flint", routes=chart_routes(store, session_of))],
    middleware=[Middleware(SessionMiddleware, secret_key=os.environ["SESSION_SECRET"])],
    lifespan=lifespan,
)
```

Two options set how long the sidecar waits. `timeout` is the seconds one check may take (10 by
default). `start_timeout` is the seconds Node may take to start (120 by default), which includes
`npx` downloading `flint-chart` the first time:

```python
sidecar = FlintSidecar(timeout=5.0, start_timeout=300.0)
```

A check that times out, or finds that Node has exited, stops the sidecar. `show_chart` then
answers the model with the problem ("Flint could not check this chart (...); call show_chart
again") and keeps no chart, so the agent's run goes on. The next check starts the sidecar again,
as long as the lifespan's `async with` is still open.

To use a `flint-chart` that you install yourself (an image built without network access, say),
install the pinned release:

```bash
npm install flint-chart@1.1.0
```

Then run the script with `node` and point `FLINT_CHART_DIR` at the package:

```python
from s_layer_flint_charts import FLINT_VERSION, VALIDATOR_SCRIPT, FlintSidecar

# with FLINT_CHART_DIR=/app/node_modules/flint-chart in the environment
sidecar = FlintSidecar(("node", str(VALIDATOR_SCRIPT), FLINT_VERSION))
```

The script checks the `flint-chart` it finds against the version in its last argument and
refuses to start on a mismatch. Without `FLINT_CHART_DIR`, it also finds a `flint-chart`
installed in `node_modules` under the working directory. Without a validator, charts are
checked by the grain guard alone.

## Limits

- A session holds its newest 20 results and 50 charts, and is forgotten an hour after the
  agent's tools last used it. The rows route doesn't count as a use, so a chart redrawn in an
  open tab still expires. Past 1,000 sessions, the least recently used is forgotten early. A
  chart whose rows have expired can't be redrawn until the query runs again. Set these with
  `ChartStore(ttl=…, max_sessions=…, max_results=…, max_charts=…)`.
- The store is in memory, per process. Run one process, or route each conversation to the same
  one.

## See also

- [Charts in a chat UI](chat-ui.md)
- [Rows and the grain guard](grain.md)
- [Mapping semantic formats to Flint](mapping.md)
