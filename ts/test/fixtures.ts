import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { ChartAssemblyInput } from "flint-chart";

// Flint inputs the Python side builds from query results (tests/test_flint_inputs.py writes them).
// Read by path: a DOM test environment replaces the global URL.
const cases: Record<string, { input: ChartAssemblyInput }> = JSON.parse(
  readFileSync(join(import.meta.dirname, "flint-inputs.json"), "utf8"),
);

/** A chart as `show_chart` answers with it: its rows by URL, and the rows the URL serves. */
export function served(name: string, url = `/flint/charts/c_${name}/rows`) {
  const input = cases[name]?.input;
  if (!input) throw new Error(`no case ${name}`);
  const rows = input.data.values as Record<string, unknown>[];
  const chart: ChartAssemblyInput = { ...input, data: { url } };
  return { chart, rows, url };
}

/** A chart the grain guard passes. */
export const GOOD = "margin_lines_by_quarter";
/** A chart Flint would merge rows for. */
export const MERGED = "orders_heatmap_channel_unplaced";

export function receipt(chart: ChartAssemblyInput, rows: number) {
  return { ok: true, chart_id: "c_1", rows_drawn: rows, chart };
}

/** A `fetch` that serves `routes` by URL, and 404 for anything else. */
export function fakeFetch(routes: Record<string, unknown>) {
  const calls: { url: string; init: RequestInit | undefined }[] = [];
  const fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, init });
    if (!(url in routes)) return new Response("not found", { status: 404 });
    return new Response(JSON.stringify(routes[url]), {
      headers: { "Content-Type": "application/json" },
    });
  };
  return { fetch: fetch as typeof globalThis.fetch, calls };
}
