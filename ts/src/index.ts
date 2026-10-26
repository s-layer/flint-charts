/**
 * Charts that `show_chart` draws, for the browser.
 *
 * `show_chart` answers with a Flint input whose `data` holds only a URL, so the rows never pass
 * through the model. This module turns that answer back into a chart Flint can draw: it reads
 * the tool result, fetches the rows and checks the chart. It needs no UI framework; the React
 * component is in `@s-layer/flint-charts/react`.
 */

import type { ChartAssemblyInput, ChartWarning } from "flint-chart";
import { validateChart } from "flint-chart/validate";

export type { ChartAssemblyInput, ChartWarning } from "flint-chart";

export const VERSION = "0.1.0";

/** The tool the Python toolset registers. */
export const SHOW_CHART_TOOL = "show_chart";

/** What the model passes to `show_chart`. */
export interface ShowChartArgs {
  result_id: string;
  chart_type: string;
  encodings: Record<string, string>;
  title: string;
  subtitle?: string;
  chart_properties?: Record<string, unknown>;
}

/** A Flint input whose rows are already in place, as Flint needs to draw it. */
export type LoadedChart = ChartAssemblyInput & { data: { values: unknown[] } };

/** `show_chart`'s answer when it drew a chart. */
export interface ChartReceipt {
  ok: true;
  chart_id: string;
  rows_drawn: number;
  /** The Flint input, its `data.url` pointing at the rows. */
  chart: ChartAssemblyInput;
  /** Flint's warnings that did not stop the chart. */
  warnings?: string[];
}

/**
 * Read `show_chart`'s result, as a chat framework hands it over: the JSON text or the parsed
 * object. Anything else, such as a refused chart the model was asked to fix, gives `null`.
 */
export function parseReceipt(result: unknown): ChartReceipt | null {
  let value = result;
  if (typeof value === "string") {
    try {
      value = JSON.parse(value);
    } catch {
      return null;
    }
  }
  if (!isObject(value) || value.ok !== true || typeof value.chart_id !== "string") return null;
  const chart = value.chart;
  if (!isObject(chart) || !isObject(chart.data) || !isObject(chart.chart_spec)) return null;
  return value as unknown as ChartReceipt;
}

/** The rows of a chart could not be fetched. */
export class ChartRowsError extends Error {
  override name = "ChartRowsError";
  /** The HTTP status, when the server answered. 404 means the rows expired or were never kept. */
  readonly status: number | undefined;

  constructor(message: string, options: { status?: number; cause?: unknown } = {}) {
    super(message, { cause: options.cause });
    this.status = options.status;
  }
}

/** Flint would draw a different chart than the one the server checked. */
export class ChartProblemError extends Error {
  override name = "ChartProblemError";
  readonly problems: readonly string[];

  constructor(problems: readonly string[]) {
    super(`The chart cannot be drawn: ${problems.join("; ")}`);
    this.problems = problems;
  }
}

export interface LoadChartOptions {
  /** Fetches the rows. Default: the global `fetch`. */
  fetch?: typeof fetch;
  /**
   * Request options for the rows, such as headers the app's route needs. The default sends
   * cookies to the same origin only, which is how the rows route tells conversations apart.
   */
  init?: RequestInit;
  signal?: AbortSignal;
}

/**
 * Fetch the rows a chart's `data.url` points at and put them in `data.values`.
 *
 * A chart whose rows are already inline comes back as it is.
 *
 * @throws {ChartRowsError} The request failed, or did not answer with a JSON array.
 */
export async function loadChart(
  chart: ChartAssemblyInput,
  options: LoadChartOptions = {},
): Promise<LoadedChart> {
  if (Array.isArray(chart.data.values)) return chart as LoadedChart;
  const url = chart.data.url;
  if (typeof url !== "string") throw new ChartRowsError("The chart has neither rows nor a URL");
  const fetchRows = options.fetch ?? globalThis.fetch;
  const init: RequestInit = { credentials: "same-origin", ...options.init };
  const headers = new Headers(init.headers);
  if (!headers.has("Accept")) headers.set("Accept", "application/json");
  let response: Response;
  try {
    response = await fetchRows(url, {
      ...init,
      headers,
      ...(options.signal ? { signal: options.signal } : {}),
    });
  } catch (error) {
    if (options.signal?.aborted) throw error;
    throw new ChartRowsError(`The chart's rows could not be fetched from ${url}`, {
      cause: error,
    });
  }
  if (!response.ok) {
    throw new ChartRowsError(`The chart's rows answered ${response.status} from ${url}`, {
      status: response.status,
    });
  }
  let rows: unknown;
  try {
    rows = await response.json();
  } catch (error) {
    if (options.signal?.aborted) throw error;
    throw new ChartRowsError(`The chart's rows from ${url} are not JSON`, { cause: error });
  }
  if (!Array.isArray(rows)) {
    throw new ChartRowsError(`The chart's rows from ${url} are not a list`);
  }
  return { ...chart, data: { values: rows } };
}

/** What Flint says about a chart before it draws it. */
export interface ChartCheck {
  /** Why the chart must not be drawn. Empty when it may be. */
  errors: string[];
  /** Everything else Flint noticed. */
  warnings: ChartWarning[];
}

/** Warnings that stop a chart: Flint merging rows draws a different number than the result. */
const ERROR_WARNINGS = new Set(["implicit-aggregate"]);

/**
 * Check a loaded chart as Flint's Vega-Lite backend would draw it.
 *
 * The server checks each chart too, but with the rows the browser fetches, this is the check of
 * what is actually drawn. Flint errors stop the chart, and so does its `implicit-aggregate`
 * warning, which means Flint would merge rows.
 */
export function checkChart(chart: LoadedChart): ChartCheck {
  const result = validateChart(chart as ChartAssemblyInput, "vegalite");
  const errors = result.errors.map((entry) => entry.message);
  const warnings: ChartWarning[] = [];
  for (const warning of result.warnings) {
    if (ERROR_WARNINGS.has(warning.code)) errors.push(warning.message);
    else if (warning.severity !== "error") warnings.push(warning);
  }
  if (errors.length === 0 && !result.valid) errors.push("Flint cannot draw this chart");
  return { errors, warnings };
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
