# TypeScript API

Everything `@s-layer/flint-charts` exports, by entry point. For a walk-through, see
[Charts in a chat UI](chat-ui.md).

| Entry point | Needs | Holds |
|---|---|---|
| `@s-layer/flint-charts` | nothing beyond `flint-chart` | reading results, fetching rows, checking charts |
| `@s-layer/flint-charts/react` | React 18+, `vega`, `vega-lite`, `vega-tooltip` | `<SLayerChart>`, `<ShowChartToolCall>`, `useChart` |
| `@s-layer/flint-charts/copilotkit` | the above and `@copilotkit/react-core` 1.80+ | `showChartRenderer`, `useShowChartRenderer` |
| `@s-layer/flint-charts/assistant-ui` | the above and `@assistant-ui/react` 0.15 | `showChartTool` |

The package is ESM only.

## `@s-layer/flint-charts`

### `parseReceipt(result)`

Reads a `show_chart` result as a chat framework hands it over.

| Parameter | Type | Description |
|---|---|---|
| `result` | `unknown` | The tool result: the JSON text, or the object parsed from it. |

**Returns:** [`ChartReceipt`](#chartreceipt) or `null`. `null` for anything other than a drawn chart: a refused
chart (`{"ok": false, "problems": [...]}`), the retry text the model receives, or a value
of another shape.

```ts
import { parseReceipt } from "@s-layer/flint-charts";

const receipt = parseReceipt(toolCall.result);
if (receipt) console.log(`${receipt.rows_drawn} rows at ${receipt.chart.data.url}`);
```

### `ChartReceipt`

The result of a `show_chart` call that drew a chart.

| Field | Type | Description |
|---|---|---|
| `ok` | `true` | Always `true` on a receipt. |
| `chart_id` | `string` | The chart's id in the server's store. |
| `rows_drawn` | `number` | How many rows the chart draws. |
| `chart` | `ChartAssemblyInput` | The Flint input. Its `data` is `{ url }`, the rows route for this chart. |
| `warnings` | `string[]` (optional) | Flint warnings that did not stop the chart. |

### `loadChart(chart, options?)`

Fetches the rows a Flint input's `data.url` points at and returns the input with them in
`data.values`. An input whose rows are already inline comes back unchanged.

| Parameter | Type | Description |
|---|---|---|
| `chart` | `ChartAssemblyInput` | The Flint input from a receipt. |
| `options.fetch` | `typeof fetch` | Fetches the rows. Default: the global `fetch`. |
| `options.init` | `RequestInit` | Request options, spread over the default `{ credentials: "same-origin" }`. `Accept: application/json` is added when not set. |
| `options.signal` | `AbortSignal` | Cancels the request. An abort rejects with the abort's own error. |

**Returns:** a promise of a [`LoadedChart`](#loadedchart), the Flint input with
`data: { values }`.

**Throws:** [`ChartRowsError`](#chartrowserror) when the input has neither inline rows nor a
`data.url`, or when the request fails, answers with a status other than 2xx, or answers with
something other than a JSON array.

```ts
import { loadChart } from "@s-layer/flint-charts";

const loaded = await loadChart(receipt.chart, {
  init: { credentials: "include", headers: { Authorization: `Bearer ${token}` } },
});
```

### `checkChart(chart)`

Checks a loaded chart as Flint's Vega-Lite backend would draw it.

| Parameter | Type | Description |
|---|---|---|
| `chart` | `LoadedChart` | A Flint input with its rows inline. |

**Returns:** [`ChartCheck`](#chartcheck). A chart may be drawn when `errors` is empty. Flint's errors
stop a chart, and so does its `implicit-aggregate` warning, which means Flint would merge
rows into one mark.

Drawing the result without React, with Flint's Vega-Lite assembler and `vega-embed` (install
`flint-chart` and `vega-embed` as your own dependencies to import them):

```ts
import { checkChart, loadChart } from "@s-layer/flint-charts";
import { assembleVegaLite } from "flint-chart/vegalite";
import embed from "vega-embed";

const loaded = await loadChart(receipt.chart);
const { errors } = checkChart(loaded);
if (errors.length === 0) await embed("#chart", assembleVegaLite(loaded));
```

### `ChartCheck`

| Field | Type | Description |
|---|---|---|
| `errors` | `string[]` | Why the chart must not be drawn. Empty when it may be. |
| `warnings` | `ChartWarning[]` | Flint's other warnings. |

### `ChartRowsError`

Thrown by [`loadChart`](#loadchartchart-options). Extends `Error`.

| Property | Type | Description |
|---|---|---|
| `status` | `number \| undefined` | The HTTP status when the server answered. From the rows route, `404` means the chart is unknown, expired, or belongs to another conversation than the request's. |
| `cause` | `unknown` | The underlying error, such as a network failure or a JSON parse error. |

### `ChartProblemError`

The error [`useChart`](#usechartchart-options) reports for a chart
[`checkChart`](#checkchartchart) refused. Extends `Error`.

| Property | Type | Description |
|---|---|---|
| `problems` | `readonly string[]` | The `errors` from `checkChart`. |

### `LoadedChart`

`ChartAssemblyInput & { data: { values: unknown[] } }`: a Flint input with its rows inline.

### `LoadChartOptions`

The `options` of [`loadChart`](#loadchartchart-options): `fetch`, `init` and `signal`.

### `ShowChartArgs`

The arguments the model passes to `show_chart`: `result_id`, `chart_type`, `encodings`
(a result column per channel), `title`, and optionally `subtitle` and `chart_properties`.
Tool-call views receive them as `Partial<ShowChartArgs>` while the model is still writing
them.

### `SHOW_CHART_TOOL`

`"show_chart"`, the name the Python
{py:func}`chart_toolset <s_layer_flint_charts.pydantic_ai.chart_toolset>` registers the tool
under.

### `VERSION`

The package version, such as `"0.1.0"`.

### `ChartAssemblyInput`, `ChartWarning`

Re-exported from `flint-chart` for typing receipts and checks.

## `@s-layer/flint-charts/react`

### `<SLayerChart>`

Draws one Flint input: fetches its rows, checks it, then draws it with Flint's
`<FlintChart>`.

| Prop | Type | Description |
|---|---|---|
| `chart` | `ChartAssemblyInput` | The Flint input, rows by URL or inline. |
| `fetch` | `typeof fetch` | Fetches the rows. Default: the global `fetch`. |
| `requestInit` | `RequestInit` | Options for the rows request. Default: cookies to the same origin only. |
| `loading` | `ReactNode` | Shown while the rows load and Flint mounts. Default: [`<ChartSkeleton>`](#chartskeleton) with the chart's title. |
| `renderError` | `(error: Error) => ReactNode` | Shown in place of a chart whose rows could not be loaded or that failed the check. Default: [`<ChartErrorNote>`](#charterrornote). |

It also takes every `<FlintChart>` prop except `spec` and `fallback`, such as `width`,
`height`, `fit`, `renderer`, `onInteraction` and `onWarnings`. The rows are fetched once per
`data.url`: a parent may build `chart` afresh on every render.

```tsx
import { SLayerChart } from "@s-layer/flint-charts/react";

<SLayerChart chart={receipt.chart} height={360} fit="relayout" renderer="svg" />;
```

### `<ShowChartToolCall>`

Draws one `show_chart` call in a chat. The CopilotKit and assistant-ui adapters render it,
and so can a tool-call view in any other chat framework.

| Prop | Type | Description |
|---|---|---|
| `status` | [`ToolCallStatus`](#toolcallstatus) | Where the call is. |
| `args` | `Partial<ShowChartArgs>` | The arguments so far. The title shows while the chart is drawn. |
| `result` | `unknown` | The tool result, as text or parsed. Read once `status` is `"complete"`. |

It also takes every `<SLayerChart>` prop except `chart`. Before `"complete"` it shows the
loading box. After, it draws the receipt's chart, or nothing for a refused call, because the
model is asked to fix that chart and call again.

```tsx
import { ShowChartToolCall } from "@s-layer/flint-charts/react";

<ShowChartToolCall status={call.done ? "complete" : "running"} args={call.args} result={call.result} />;
```

### `ToolCallStatus`

`"streaming"` while the model writes the arguments, `"running"` while the server draws,
`"complete"` once the result arrived or the call ended without one.

### `useChart(chart, options?)`

The hook [`<SLayerChart>`](#slayerchart) uses: fetches the rows and checks the chart, once per `data.url`.

| Parameter | Type | Description |
|---|---|---|
| `chart` | `ChartAssemblyInput` | The Flint input. |
| `options.fetch` | `typeof fetch` | As on `<SLayerChart>`. |
| `options.requestInit` | `RequestInit` | As on `<SLayerChart>`. |

**Returns:** `ChartState`:

| `status` | Other fields | Meaning |
|---|---|---|
| `"loading"` | | The rows are on their way. |
| `"ready"` | `chart: LoadedChart`, `warnings: ChartWarning[]` | The chart may be drawn. |
| `"error"` | `error: Error` | A [`ChartRowsError`](#chartrowserror), a [`ChartProblemError`](#chartproblemerror), or an error Flint threw while checking. |

```tsx
import type { ChartAssemblyInput } from "@s-layer/flint-charts";
import { useChart } from "@s-layer/flint-charts/react";

function RowCount({ chart }: { chart: ChartAssemblyInput }) {
  const state = useChart(chart);
  return state.status === "ready" ? <span>{state.chart.data.values.length} rows</span> : null;
}
```

### `<ChartSkeleton>`

The default loading box: a `role="status"` box with `aria-busy="true"` and the title, class
`slayer-chart-skeleton`. Props: `title?: string`, `style?: CSSProperties`.

### `<ChartErrorNote>`

The default error note: a `role="alert"` box with
[`describeError(error)`](#describeerrorerror), class
`slayer-chart-error`. Props: `error: Error`, `style?: CSSProperties`.

### `describeError(error)`

Returns the text a reader sees for an error:

| Error | Text |
|---|---|
| `ChartRowsError` with status 404 | "This chart's data has expired. Ask for it again to redraw it." |
| Any other `ChartRowsError` | "This chart's data could not be loaded." |
| Anything else | "This chart could not be drawn." |

```tsx
import { describeError, SLayerChart } from "@s-layer/flint-charts/react";

<SLayerChart chart={chart} renderError={(error) => <Toast>{describeError(error)}</Toast>} />;
```

### `SLayerChartProps`, `ShowChartToolCallProps`, `UseChartOptions`, `ChartSkeletonProps`, `ChartErrorNoteProps`

The prop and option types above.

## `@s-layer/flint-charts/copilotkit`

Uses CopilotKit's v2 API (`@copilotkit/react-core/v2`).

### `showChartRenderer(options?)`

A tool-call renderer for `CopilotKitProvider`'s `renderToolCalls`.

| Option | Type | Description |
|---|---|---|
| `name` | `string` | The tool name. Default: `"show_chart"`. |
| `agentId` | `string` | Draw only this agent's calls. |

It also takes every `<ShowChartToolCall>` prop except `status`, `args` and `result`.

```tsx
import { CopilotKitProvider } from "@copilotkit/react-core/v2";
import { showChartRenderer } from "@s-layer/flint-charts/copilotkit";

const renderers = [showChartRenderer({ height: 360 })];

<CopilotKitProvider runtimeUrl="/api/copilotkit" renderToolCalls={renderers}>{children}</CopilotKitProvider>;
```

### `useShowChartRenderer(options?)`

Registers the same renderer from a component inside the provider. It takes the same
options. A call draws with the options of the hook's latest render, so a new width or token
applies to calls drawn after it.

```tsx
import { useShowChartRenderer } from "@s-layer/flint-charts/copilotkit";

function Charts({ token }: { token: string }) {
  useShowChartRenderer({ requestInit: { headers: { Authorization: `Bearer ${token}` } } });
  return null;
}
```

### `ShowChartRendererOptions`

The options type above.

## `@s-layer/flint-charts/assistant-ui`

### `showChartTool(options?)`

The toolkit entry for `show_chart`: a backend tool (`type: "backend"`) drawn on its own,
outside the run of tool calls the chat may fold together (`display: "standalone"`). The
tool's name is its key in the toolkit.

It takes every `<ShowChartToolCall>` prop except `status`, `args` and `result`. A call that
ends without a result, cancelled or failed, shows nothing.

```tsx
import { defineToolkit } from "@assistant-ui/react";
import { showChartTool } from "@s-layer/flint-charts/assistant-ui";

const toolkit = defineToolkit({ show_chart: showChartTool({ height: 360 }) });
```

### `ShowChartToolOptions`

The options type above.

## See also

- [Charts in a chat UI](chat-ui.md)
- [Charts in an agent](agents.md)
