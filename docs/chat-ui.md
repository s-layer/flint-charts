# Charts in a chat UI

`@s-layer/flint-charts` draws the charts `show_chart` answers with. It fetches each chart's rows
from the URL in its `data`, checks the chart with Flint, and draws it with Flint's own
`<FlintChart>`. The adapters for CopilotKit and assistant-ui draw every `show_chart` call in the
chat: a box with the chart's title while the server draws it, then the chart.

```bash
npm install @s-layer/flint-charts vega vega-lite vega-tooltip
```

`vega`, `vega-lite` and `vega-tooltip` are the peer dependencies Flint draws with. The package
needs React 18 or later. Its components are client components (the built files say
`"use client"`), so in Next.js render them from client code.

## Reach the rows route

Each chart's `data.url` is a path such as `/flint/charts/c_1KZ…/rows`, so the browser asks the
server that served the page. Mount [the rows route](agents.md#the-rows-route) on your Python
app, then make that path reach it in one of two ways:

- **Same origin (simplest).** Serve the page and the Python app from one origin, or proxy
  `/flint` to the Python app: `server.proxy` in Vite, `rewrites` in Next.js, or your reverse
  proxy. The default rows request then works as it is.
- **Another origin.** Pass an absolute `url_prefix`, such as
  `url_prefix="https://api.example.com/flint"`, to `chart_toolset`, allow the page's origin in
  the Python app's CORS settings with credentials allowed, and set
  `requestInit: { credentials: "include" }` (see
  [below](#send-credentials-or-headers-with-the-rows-request)). A session cookie sent this way
  needs `SameSite=None; Secure`.

Either way, the rows request must carry whatever your `session_of` reads, usually a session
cookie, and it must name the same conversation the agent run used as its `session_id`. A
chart that answers "This chart's data has expired" on its first draw usually means the request
did not reach the route, or arrived without that conversation.

## CopilotKit

Pass the renderer to the provider:

```tsx
import { CopilotChat, CopilotKitProvider } from "@copilotkit/react-core/v2";
import { showChartRenderer } from "@s-layer/flint-charts/copilotkit";

export function App() {
  return (
    <CopilotKitProvider runtimeUrl="/api/copilotkit" renderToolCalls={[showChartRenderer()]}>
      <CopilotChat />
    </CopilotKitProvider>
  );
}
```

Or register it from a component inside the provider with
[`useShowChartRenderer()`](typescript.md#useshowchartrendereroptions).

## assistant-ui

`show_chart` runs on the server, so its toolkit entry is a backend tool with a renderer:

```tsx
import { defineToolkit } from "@assistant-ui/react";
import { showChartTool } from "@s-layer/flint-charts/assistant-ui";

const toolkit = defineToolkit({ show_chart: showChartTool() });
```

Register the toolkit on the provider's `config`:

```tsx
import { AssistantRuntimeProvider, AuiConfig, Tools } from "@assistant-ui/react";

const config = AuiConfig({ tools: Tools({ toolkit }) });

<AssistantRuntimeProvider runtime={runtime} config={config}>{children}</AssistantRuntimeProvider>;
```

The chart is drawn on its own, outside the run of tool calls the chat may fold together.

## Any other UI

[`<SLayerChart>`](typescript.md#slayerchart) draws one chart from the `chart` in a
`show_chart` result:

```tsx
import { parseReceipt } from "@s-layer/flint-charts";
import { SLayerChart } from "@s-layer/flint-charts/react";

export function ChartResult({ toolResult }: { toolResult: unknown }) {
  const receipt = parseReceipt(toolResult); // the JSON text or the parsed object
  return receipt ? <SLayerChart chart={receipt.chart} height={360} /> : null;
}
```

[`parseReceipt`](typescript.md#parsereceiptresult) gives `null` for a chart the server
refused. The model is told what to fix and calls `show_chart` again, so the chat shows nothing
for the refused call.

Without React, [`loadChart`](typescript.md#loadchartchart-options) fetches the rows into
`data.values` and [`checkChart`](typescript.md#checkchartchart) runs Flint's checks, and you
draw the result with any Flint backend.

Every adapter and `<SLayerChart>` also take any `<FlintChart>` prop but `spec` and `fallback`,
such as `width`, `height`, `fit`, `renderer` or `onInteraction`. The CopilotKit adapters also
take `name`, for a toolset that registers the tool under another name, and `agentId`. In
assistant-ui the tool's name is its `defineToolkit` key. See [TypeScript API](typescript.md)
for every option.

## Send credentials or headers with the rows request

By default the rows request sends cookies to the same origin only, which is how the rows route
tells conversations apart. Pass `requestInit` to any adapter or to `<SLayerChart>` to add a
header, or set `credentials: "include"` for a rows route on another origin:

```tsx
import { showChartRenderer } from "@s-layer/flint-charts/copilotkit";

const renderer = showChartRenderer({
  requestInit: { credentials: "include", headers: { Authorization: `Bearer ${token}` } },
});
```

To fetch the rows some other way, pass `fetch`, which replaces the global `fetch`.

## Change the loading box and the error note

Pass either option to any adapter or to `<SLayerChart>`:

- `loading`: shown while the rows load. By default, a box with the chart's title.
- `renderError`: shown in place of a chart whose rows could not be loaded or that failed
  Flint's check. By default, a short note with one of the messages below.

The defaults, [`<ChartSkeleton>`](typescript.md#chartskeleton) and
[`<ChartErrorNote>`](typescript.md#charterrornote), set their background, padding and corners
inline, so to restyle them pass your own `loading` and `renderError`.
[`describeError`](typescript.md#describeerrorerror) gives the default note's text for your own
error component. The defaults carry the classes `slayer-chart-skeleton` and
`slayer-chart-error` for selecting them, such as in tests.

## What the reader sees when a chart can't be drawn

- The rows route answers 404: "This chart's data has expired. Ask for it again to redraw it."
  The route answers 404 for a chart that has expired, and also for a request that does not
  carry the conversation the chart belongs to. By default the store keeps a conversation's
  newest 50 charts, until an hour after its last use (see [Limits](agents.md#limits)).
- The rows could not be fetched: "This chart's data could not be loaded."
- Flint would draw something other than the rows, such as merging rows into one mark: "This
  chart could not be drawn." The server checks each chart before it answers, so this means the
  rows changed or the server ran without a validator.
- Flint fails while it mounts a chart that passed its check: Flint shows its own muted error
  box in the chart's place, and `renderError` is not used. Pass `onError` to hear about it.

## See also

- [TypeScript API](typescript.md)
- [Charts in an agent](agents.md)
- [Rows and the grain guard](grain.md)
