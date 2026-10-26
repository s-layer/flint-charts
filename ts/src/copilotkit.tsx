/**
 * Draw `show_chart` calls in a CopilotKit chat.
 *
 * Pass the renderer to the provider, or register it from a component with the hook:
 *
 * ```tsx
 * <CopilotKitProvider runtimeUrl="/api/copilotkit" renderToolCalls={[showChartRenderer()]}>
 * ```
 */

import { defineToolCallRenderer, useRenderTool } from "@copilotkit/react-core/v2";
import { useRef } from "react";
import { SHOW_CHART_TOOL, type ShowChartArgs } from "./index.js";
import { ShowChartToolCall, type ShowChartToolCallProps, type ToolCallStatus } from "./react.js";
import { showChartArgs } from "./schema.js";

export interface ShowChartRendererOptions
  extends Omit<ShowChartToolCallProps, "status" | "args" | "result"> {
  /** The tool's name, if the agent registers it under another. Default: `show_chart`. */
  name?: string;
  /** Draw only this agent's calls. */
  agentId?: string;
}

type RenderProps = {
  status: "inProgress" | "executing" | "complete";
  args: Partial<ShowChartArgs>;
  result: string | undefined;
};

/** A tool-call renderer for `CopilotKitProvider`'s `renderToolCalls`. */
export function showChartRenderer(options: ShowChartRendererOptions = {}) {
  const { name = SHOW_CHART_TOOL, agentId, ...props } = options;
  return defineToolCallRenderer({
    name,
    args: showChartArgs,
    render: (call: RenderProps) => (
      <ShowChartToolCall
        {...props}
        status={STATUS[call.status]}
        args={call.args}
        result={call.result}
      />
    ),
    ...(agentId === undefined ? {} : { agentId }),
  });
}

/**
 * Register the `show_chart` renderer from inside a CopilotKit provider. A call draws with the
 * options of the hook's latest render, such as a new width or token.
 */
export function useShowChartRenderer(options: ShowChartRendererOptions = {}): void {
  const { name = SHOW_CHART_TOOL, agentId, ...props } = options;
  const latest = useRef(props);
  latest.current = props;
  useRenderTool(
    {
      name,
      parameters: showChartArgs,
      render: (call: {
        status: RenderProps["status"];
        parameters: Partial<ShowChartArgs>;
        result: string | undefined;
      }) => (
        <ShowChartToolCall
          {...latest.current}
          status={STATUS[call.status]}
          args={call.parameters}
          result={call.result}
        />
      ),
      ...(agentId === undefined ? {} : { agentId }),
    },
    [name, agentId],
  );
}

const STATUS: Record<RenderProps["status"], ToolCallStatus> = {
  inProgress: "streaming",
  executing: "running",
  complete: "complete",
};
