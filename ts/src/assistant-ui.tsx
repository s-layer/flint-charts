/**
 * Draw `show_chart` calls in an assistant-ui chat.
 *
 * `show_chart` runs on the server, so its toolkit entry is a backend tool with a renderer:
 *
 * ```tsx
 * const toolkit = defineToolkit({ show_chart: showChartTool() });
 * ```
 */

import type { ToolCallMessagePartProps, ToolDefinition } from "@assistant-ui/react";
import type { ShowChartArgs } from "./index.js";
import { ShowChartToolCall, type ShowChartToolCallProps } from "./react.js";

export type ShowChartToolOptions = Omit<ShowChartToolCallProps, "status" | "args" | "result">;

/** The toolkit entry for `show_chart`: drawn on its own, outside the chain of tool calls. */
export function showChartTool(
  options: ShowChartToolOptions = {},
): ToolDefinition<Partial<ShowChartArgs> & Record<string, unknown>, unknown> {
  return {
    type: "backend",
    display: "standalone",
    render: (part: ToolCallMessagePartProps<Partial<ShowChartArgs>, unknown>) => (
      <ShowChartToolCall {...options} status={status(part)} args={part.args} result={part.result} />
    ),
  };
}

function status(part: ToolCallMessagePartProps<Partial<ShowChartArgs>, unknown>) {
  return part.result !== undefined && !part.isPreliminary ? "complete" : "running";
}
