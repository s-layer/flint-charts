# Charts in a chat UI

`@s-layer/flint-charts` draws the charts `show_chart` answers with. It fetches each chart's rows
from the URL in its `data`, checks the chart with Flint, and draws it with Flint's own
`<FlintChart>`. The adapters for CopilotKit and assistant-ui draw every `show_chart` call in the
chat: a box with the chart's title while the server draws it, then the chart.

```bash
npm install @s-layer/flint-charts vega vega-lite vega-tooltip
```

It needs React 18 or later. Mount the rows route on your server first (see
[the rows route](agents.md#the-rows-route)).

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

Or register it from a component inside the provider with `useShowChartRenderer()`.

## assistant-ui

`show_chart` runs on the server, so its toolkit entry is a backend tool with a renderer:

```tsx
import { defineToolkit } from "@assistant-ui/react";
import { showChartTool } from "@s-layer/flint-charts/assistant-ui";

const toolkit = defineToolkit({ show_chart: showChartTool() });
```

The chart is drawn on its own, outside the run of tool calls the chat may fold together.

## Any other UI

`<SLayerChart>` draws one chart from the `chart` in a `show_chart` result:

```tsx
import { parseReceipt } from "@s-layer/flint-charts";
import { SLayerChart } from "@s-layer/flint-charts/react";

const receipt = parseReceipt(toolResult); // the JSON text or the parsed object
if (receipt) return <SLayerChart chart={receipt.chart} height={360} />;
```

`parseReceipt` gives `null` for a chart the server refused. The model is told what to fix and
calls `show_chart` again, so the chat shows nothing for the refused call.

Without React, `loadChart` fetches the rows into `data.values` and `checkChart` runs Flint's
checks, and you draw the result with any Flint backend.

## Options

Every adapter and `<SLayerChart>` take the same options:

- Any `<FlintChart>` prop but `spec` and `fallback` (use `loading`), such as `width`,
  `height`, `fit`, `renderer` or `onInteraction`.
- `requestInit`: options for the rows request. By default it sends cookies to the same origin
  only, which is how the rows route tells conversations apart. Use it to add a header, or
  `credentials: "include"` for a route on another origin.
- `fetch`: fetches the rows in place of the global `fetch`.
- `loading`: shown while the rows load. By default, a box with the chart's title.
- `renderError`: shown in place of a chart that cannot be drawn. By default, a short note.

The CopilotKit adapters also take `name`, for a toolset that registers the tool under another
name, and `agentId`. In assistant-ui the tool's name is its `defineToolkit` key.

## What the reader sees when a chart can't be drawn

- The rows have expired (the route answers 404): "This chart's data has expired. Ask for it
  again to redraw it." The store keeps a session's charts for an hour after its last use.
- The rows could not be fetched: "This chart's data could not be loaded."
- Flint would draw something other than the rows, such as merging rows into one mark: "This
  chart could not be drawn." The server checks each chart before it answers, so this means the
  rows changed or the server ran without a validator.

The default boxes have the classes `slayer-chart-skeleton` and `slayer-chart-error` for your
stylesheet.

## See also

- [Charts in an agent](agents.md)
- [Rows and the grain guard](grain.md)
