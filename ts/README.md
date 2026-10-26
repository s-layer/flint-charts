# @s-layer/flint-charts

Draws the charts that the `show_chart` tool from
[`s-layer-flint-charts`](https://pypi.org/project/s-layer-flint-charts/) answers with, in
CopilotKit, assistant-ui or plain React.

`show_chart` answers with a [Flint](https://github.com/microsoft/flint-chart) input, a chart
whose rows stay on the server behind a URL. This package fetches those rows, checks the chart
with Flint and draws it with Flint's `<FlintChart>`.

```bash
npm install @s-layer/flint-charts vega vega-lite vega-tooltip
```

`vega`, `vega-lite` and `vega-tooltip` are the peer dependencies Flint draws with. The React
entry points need React 18 or later.

## CopilotKit

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

## assistant-ui

```tsx
import { AssistantRuntimeProvider, AuiConfig, defineToolkit, Tools } from "@assistant-ui/react";
import { showChartTool } from "@s-layer/flint-charts/assistant-ui";

const toolkit = defineToolkit({ show_chart: showChartTool() });
const config = AuiConfig({ tools: Tools({ toolkit }) });

<AssistantRuntimeProvider runtime={runtime} config={config}>
  {children}
</AssistantRuntimeProvider>;
```

## React

```tsx
import { parseReceipt } from "@s-layer/flint-charts";
import { SLayerChart } from "@s-layer/flint-charts/react";

export function ChartResult({ toolResult }: { toolResult: unknown }) {
  const receipt = parseReceipt(toolResult);
  return receipt ? <SLayerChart chart={receipt.chart} height={360} /> : null;
}
```

The rows URL must reach the Python app's rows route with the conversation's session. See
[Charts in a chat UI](https://s-layer.github.io/flint-charts/chat-ui.html) for the options
and what a reader sees when a chart can't be drawn.

## License

MIT
