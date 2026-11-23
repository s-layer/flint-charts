# Charts in a chat UI

[Flint](https://github.com/microsoft/flint-chart) is Microsoft's semantic chart library: a Flint
input names a chart type, a column per channel and a semantic type per column, and Flint turns it
into a chart, with Vega-Lite by default.

`@s-layer/flint-charts` draws the charts `show_chart` answers with. It fetches each chart's rows
from the URL in its `data`, checks the chart with Flint, and draws it with Flint's own
`<FlintChart>`. The adapters for CopilotKit and assistant-ui draw every `show_chart` call in the
chat: a box with the chart's title while the server draws it, then the chart.

```bash
npm install @s-layer/flint-charts
```

The package installs Flint for you (`flint-chart`, pinned to exactly 1.1.0), and Flint brings the
chart libraries it draws with. Its peers are all optional: `react` 18 or later for the React,
CopilotKit and assistant-ui entry points, `@copilotkit/react-core` ^1.80.0 for CopilotKit, and
`@assistant-ui/react` ^0.15.0 for assistant-ui. Install the ones your entry points use.

The React components are client components (the built files say `"use client"`), so in Next.js
render them from client code. Upgrading from `@s-layer/flint-charts` 0.1.0? See
[Upgrading from 0.2.0](upgrading.md#the-npm-package).

## Reach the rows route

Each chart's `data.url` is a path such as `/flint/charts/c_1KZ…/rows`, so the browser asks the
server that served the page. Mount [the rows route](agents.md#the-rows-route) on your Python
app, then make that path reach it in one of two ways:

- **Same origin (simplest).** Serve the page and the Python app from one origin, or proxy
  `/flint` to the Python app: `server.proxy` in Vite, `rewrites` in Next.js, or your reverse
  proxy. The default rows request then works as it is.
- **Another origin.** Pass an absolute
  {py:func}`url_prefix <s_layer_flint_charts.pydantic_ai.chart_toolset>`, such as
  `url_prefix="https://api.example.com/flint"`, to
  {py:func}`chart_toolset <s_layer_flint_charts.pydantic_ai.chart_toolset>`. The rows route does
  no CORS handling of its own, so in the Python app's CORS settings allow the page's origin, allow
  credentials, and allow every header that you add to the rows request, such as `Authorization`.
  Without the header allowed, the browser's preflight fails and every chart shows "This chart's data could not
  be loaded." Then set `requestInit: { credentials: "include" }` (see
  [below](#send-credentials-or-headers-with-the-rows-request)). A session cookie sent this way needs
  `SameSite=None; Secure`.

  With Starlette's `CORSMiddleware`, for example:

  ```python
  from starlette.middleware import Middleware
  from starlette.middleware.cors import CORSMiddleware

  middleware = [
      Middleware(
          CORSMiddleware,
          allow_origins=["https://app.example.com"],
          allow_credentials=True,
          allow_headers=["Authorization"],
      )
  ]
  ```

Either way, the rows request must carry whatever your
{py:func}`session_of <s_layer_flint_charts.server.chart_routes>` reads, usually a session
cookie, and it must name the same conversation the agent run used as its `session_id`. If a
chart shows "This chart's data has expired" on its first draw, the request usually did not
reach the route, or arrived without that conversation.

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
tells conversations apart. Pass [`requestInit`](typescript.md#slayerchart) to any adapter or to
`<SLayerChart>` to add a header, or set `credentials: "include"` for a rows route on another
origin:

```tsx
import { showChartRenderer } from "@s-layer/flint-charts/copilotkit";

const renderer = showChartRenderer({
  requestInit: { credentials: "include", headers: { Authorization: `Bearer ${token}` } },
});
```

To fetch the rows some other way, pass [`fetch`](typescript.md#slayerchart), which replaces the
global `fetch`.

If your token changes, mind when the rows are fetched: once per chart, with the options in place
at that moment. In CopilotKit,
[`useShowChartRenderer()`](typescript.md#useshowchartrendereroptions) picks up new options on
each render. In assistant-ui, `showChartTool` takes its options once, when you define the
toolkit, so a header in `requestInit` sends the token you gave it then. Pass a `fetch` that reads the
current token on each request instead:

```tsx
import { defineToolkit } from "@assistant-ui/react";
import { showChartTool } from "@s-layer/flint-charts/assistant-ui";

let token = "";
export function setToken(next: string) {
  token = next; // call this whenever your auth layer refreshes the token
}

const toolkit = defineToolkit({
  show_chart: showChartTool({
    fetch: (input, init) => {
      const headers = new Headers(init?.headers);
      headers.set("Authorization", `Bearer ${token}`);
      return fetch(input, { ...init, headers });
    },
  }),
});
```

## Change the loading box and the error note

Pass either option to any adapter or to `<SLayerChart>`:

- [`loading`](typescript.md#slayerchart): shown while the rows load. By default, a box with the
  chart's title, sized to the `width` and `height` that you pass.
- [`renderError`](typescript.md#slayerchart): shown in place of a chart whose rows could not be
  loaded or that failed Flint's check. By default, a short note with one of the messages below.

The defaults, [`<ChartSkeleton>`](typescript.md#chartskeleton) and
[`<ChartErrorNote>`](typescript.md#charterrornote), set their background, padding and corners
inline, so to restyle them pass your own `loading` and `renderError`.
[`describeError`](typescript.md#describeerrorerror) gives the default note's text for your own
error component. The defaults have the classes `slayer-chart-skeleton` and
`slayer-chart-error` for selecting them, such as in tests.

A replacement `loading` is one fixed node. An adapter shows that same node for every chart, so it
doesn't get each chart's title or size. To restyle the box and keep the title, render each call
yourself with [`<ShowChartToolCall>`](typescript.md#showcharttoolcall), which has the call's
arguments, and build a `<ChartSkeleton>` from them:

```tsx
import {
  ChartSkeleton,
  ShowChartToolCall,
  type ShowChartToolCallProps,
} from "@s-layer/flint-charts/react";

export function BrandedChartCall(props: ShowChartToolCallProps) {
  return (
    <ShowChartToolCall
      {...props}
      height={360}
      loading={
        <ChartSkeleton title={props.args?.title} style={{ height: 360, background: "#f3efe6" }} />
      }
    />
  );
}
```

Use it as the tool-call view in your chat framework, as in [Any other UI](#any-other-ui).

## Charts that can't be drawn

- If the server refused the chart, the chat shows nothing for that call. The model is told what to
  fix and calls `show_chart` again, so the next call can draw it.
- If the call ended without a result, because it was cancelled or failed, nothing is shown.
- The rows route answers 404: "This chart's data has expired. Ask for it again to redraw it."
  The route answers 404 for a chart that has expired, and also for a request without the
  chart's conversation. By default the store keeps a conversation's
  newest 50 charts, until an hour after the agent last used it or until more than 1,000
  conversations push it out. Drawing a chart does not count as a use (see
  [Limits](agents.md#limits)).
- The rows could not be fetched: "This chart's data could not be loaded."
- Flint would draw something other than the rows, such as merging rows into one mark: "This
  chart could not be drawn." The server checks each chart before it answers, so either the rows
  changed or the server ran without a
  [validator](agents.md#checking-charts-with-flint).
- Flint fails while it mounts a chart that passed its check: Flint shows its own muted error
  box in the chart's place, and `renderError` is not used. Pass `onError` to hear about it.

## See also

- [TypeScript API](typescript.md)
- [Charts in an agent](agents.md)
- [Rows and the grain guard](grain.md)
