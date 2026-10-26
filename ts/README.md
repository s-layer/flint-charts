# @s-layer/flint-charts

Draws the charts that the `show_chart` tool from
[`s-layer-flint-charts`](https://pypi.org/project/s-layer-flint-charts/) answers with, in
CopilotKit, assistant-ui or plain React.

`show_chart` answers with a [Flint](https://github.com/microsoft/flint-chart) chart whose rows
stay on the server behind a URL. This package fetches those rows, checks the chart with Flint
and draws it with Flint's `<FlintChart>`.

```bash
npm install @s-layer/flint-charts vega vega-lite vega-tooltip
```

## CopilotKit

```tsx
import { CopilotKitProvider } from "@copilotkit/react-core/v2";
import { showChartRenderer } from "@s-layer/flint-charts/copilotkit";

<CopilotKitProvider runtimeUrl="/api/copilotkit" renderToolCalls={[showChartRenderer()]}>
```

## assistant-ui

```tsx
import { defineToolkit } from "@assistant-ui/react";
import { showChartTool } from "@s-layer/flint-charts/assistant-ui";

const toolkit = defineToolkit({ show_chart: showChartTool() });
```

## React

```tsx
import { parseReceipt } from "@s-layer/flint-charts";
import { SLayerChart } from "@s-layer/flint-charts/react";

const receipt = parseReceipt(toolResult);
if (receipt) return <SLayerChart chart={receipt.chart} height={360} />;
```

See [Charts in a chat UI](https://s-layer.github.io/flint-charts/chat-ui.html) for the options
and what a reader sees when a chart can't be drawn.

## License

MIT
