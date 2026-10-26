"use client";

/**
 * The React chart for `show_chart`'s answers, and the tool-call view the chat adapters share.
 */

import type { ChartAssemblyInput, ChartWarning } from "flint-chart";
import { FlintChart, type FlintChartProps } from "flint-chart/react";
import { type CSSProperties, type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import {
  ChartProblemError,
  ChartRowsError,
  checkChart,
  type LoadChartOptions,
  type LoadedChart,
  loadChart,
  parseReceipt,
  type ShowChartArgs,
} from "./index.js";

/** Where a chart is on its way to the screen. */
export type ChartState =
  | { status: "loading" }
  | { status: "ready"; chart: LoadedChart; warnings: ChartWarning[] }
  | { status: "error"; error: Error };

export interface UseChartOptions {
  /** Fetches the rows. Default: the global `fetch`. */
  fetch?: typeof fetch;
  /** Request options for the rows. Default: cookies to the same origin only. */
  requestInit?: RequestInit;
}

/**
 * Fetch a chart's rows and check it, once per chart.
 *
 * A chart is the same chart while its `data.url` is, so a parent may build the input afresh on
 * every render (as a tool-call view parsing its result does) without fetching again.
 */
export function useChart(chart: ChartAssemblyInput, options: UseChartOptions = {}): ChartState {
  const [state, setState] = useState<ChartState>({ status: "loading" });
  const latest = useRef({ chart, options });
  latest.current = { chart, options };
  const key: unknown = chart.data.url ?? chart.data.values;

  // biome-ignore lint/correctness/useExhaustiveDependencies: the chart is keyed by its rows' URL.
  useEffect(() => {
    const controller = new AbortController();
    const { chart, options } = latest.current;
    const load: LoadChartOptions = { signal: controller.signal };
    if (options.fetch) load.fetch = options.fetch;
    if (options.requestInit) load.init = options.requestInit;
    setState({ status: "loading" });
    loadChart(chart, load)
      .then((loaded) => {
        if (controller.signal.aborted) return;
        const check = checkChart(loaded);
        setState(
          check.errors.length > 0
            ? { status: "error", error: new ChartProblemError(check.errors) }
            : { status: "ready", chart: loaded, warnings: check.warnings },
        );
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setState({
          status: "error",
          error: error instanceof Error ? error : new Error(String(error)),
        });
      });
    return () => controller.abort();
  }, [key]);

  return state;
}

export interface SLayerChartProps
  extends Omit<FlintChartProps, "spec" | "fallback">,
    UseChartOptions {
  /** The Flint input `show_chart` answered with, rows by URL or inline. */
  chart: ChartAssemblyInput;
  /** Shown while the rows load and Flint mounts. Default: a box with the chart's title. */
  loading?: ReactNode;
  /** Shown in place of a chart that cannot be drawn. Default: a short note. */
  renderError?: (error: Error) => ReactNode;
}

/**
 * A chart `show_chart` drew: fetches its rows, checks it with Flint, and draws it with Flint's
 * own `<FlintChart>`.
 *
 * Takes every `<FlintChart>` prop but `spec` and `fallback` (`loading` stands in for it), such
 * as `width`, `height`, `fit` and `onInteraction`.
 */
export function SLayerChart({
  chart,
  fetch,
  requestInit,
  loading,
  renderError,
  ...flint
}: SLayerChartProps): ReactNode {
  const options: UseChartOptions = {};
  if (fetch) options.fetch = fetch;
  if (requestInit) options.requestInit = requestInit;
  const state = useChart(chart, options);
  const box = boxStyle(flint.width, flint.height);
  const placeholder = loading ?? <ChartSkeleton title={chart.chart_spec.title} style={box} />;
  if (state.status === "loading") return placeholder;
  if (state.status === "error") {
    return renderError ? (
      renderError(state.error)
    ) : (
      <ChartErrorNote error={state.error} style={box} />
    );
  }
  return <FlintChart {...flint} spec={state.chart} fallback={placeholder} />;
}

/** How a chat framework says where a tool call is. */
export type ToolCallStatus = "streaming" | "running" | "complete";

export interface ShowChartToolCallProps extends Omit<SLayerChartProps, "chart"> {
  /** `streaming` while the model writes the arguments, `running` while the server draws. */
  status: ToolCallStatus;
  /** The arguments so far. */
  args?: Partial<ShowChartArgs> | undefined;
  /** The tool's result, as text or parsed. */
  result?: unknown;
}

/**
 * A `show_chart` call in a chat: a box with the title while the chart is being drawn, then the
 * chart. A call the server refused shows nothing, since the model is told to fix it and call
 * again.
 */
export function ShowChartToolCall({
  status,
  args,
  result,
  ...props
}: ShowChartToolCallProps): ReactNode {
  const receipt = useMemo(
    () => (status === "complete" ? parseReceipt(result) : null),
    [status, result],
  );
  if (status !== "complete") {
    return (
      props.loading ?? (
        <ChartSkeleton title={args?.title} style={boxStyle(props.width, props.height)} />
      )
    );
  }
  if (!receipt) return null;
  return <SLayerChart {...props} chart={receipt.chart} />;
}

export interface ChartSkeletonProps {
  title?: string | undefined;
  style?: CSSProperties;
}

/** The box a chart takes while it is on its way. Style it with the `slayer-chart-skeleton` class. */
export function ChartSkeleton({ title, style }: ChartSkeletonProps): ReactNode {
  return (
    <div
      className="slayer-chart-skeleton"
      role="status"
      aria-busy="true"
      aria-label={title ? `Drawing ${title}` : "Drawing a chart"}
      style={{ ...SKELETON, ...style }}
    >
      {title ? <span style={TITLE}>{title}</span> : null}
    </div>
  );
}

export interface ChartErrorNoteProps {
  error: Error;
  style?: CSSProperties;
}

/** Why a chart is missing, in words for the reader. Style it with the `slayer-chart-error` class. */
export function ChartErrorNote({ error, style }: ChartErrorNoteProps): ReactNode {
  return (
    <div className="slayer-chart-error" role="alert" style={{ ...NOTE, ...style }}>
      {describeError(error)}
    </div>
  );
}

/** A reader's account of why a chart is missing. */
export function describeError(error: Error): string {
  if (error instanceof ChartRowsError && error.status === 404) {
    return "This chart's data has expired. Ask for it again to redraw it.";
  }
  if (error instanceof ChartRowsError) return "This chart's data could not be loaded.";
  return "This chart could not be drawn.";
}

function boxStyle(width: number | string | undefined, height: number | string | undefined) {
  const style: CSSProperties = {};
  if (width !== undefined) style.width = width;
  if (height !== undefined) style.height = height;
  return style;
}

const SKELETON: CSSProperties = {
  boxSizing: "border-box",
  minHeight: 240,
  padding: 12,
  borderRadius: 6,
  background: "rgba(127, 127, 127, 0.08)",
};

const TITLE: CSSProperties = { fontWeight: 600, opacity: 0.6 };

const NOTE: CSSProperties = {
  boxSizing: "border-box",
  padding: 12,
  borderRadius: 6,
  background: "rgba(127, 127, 127, 0.08)",
  opacity: 0.8,
};
