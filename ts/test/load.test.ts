import { describe, expect, it } from "vitest";
import {
  ChartRowsError,
  checkChart,
  type LoadedChart,
  loadChart,
  parseReceipt,
} from "../src/index.js";
import { fakeFetch, GOOD, MERGED, receipt, served } from "./fixtures.js";

describe("parseReceipt", () => {
  const { chart } = served(GOOD);

  it("reads the receipt as JSON text", () => {
    expect(parseReceipt(JSON.stringify(receipt(chart, 6)))?.chart).toEqual(chart);
  });

  it("reads the receipt as an object", () => {
    expect(parseReceipt(receipt(chart, 6))?.chart_id).toBe("c_1");
  });

  it.each([
    ["a refused chart", { ok: false, problems: ["put region on a channel"] }],
    ["a retry prompt", "The chart was not drawn:\n- put region on a channel"],
    ["a receipt without a chart", { ok: true, chart_id: "c_1" }],
    ["a chart without data", { ok: true, chart_id: "c_1", chart: { chart_spec: {} } }],
    ["nothing", undefined],
    ["a list", [1, 2]],
  ])("gives null for %s", (_name, result) => {
    expect(parseReceipt(result)).toBeNull();
  });
});

describe("loadChart", () => {
  it("puts the rows the URL serves in data.values", async () => {
    const { chart, rows, url } = served(GOOD);
    const { fetch } = fakeFetch({ [url]: rows });
    const loaded = await loadChart(chart, { fetch });
    expect(loaded.data).toEqual({ values: rows });
    expect(loaded.chart_spec).toEqual(chart.chart_spec);
  });

  it("sends cookies to the same origin and asks for JSON", async () => {
    const { chart, rows, url } = served(GOOD);
    const { fetch, calls } = fakeFetch({ [url]: rows });
    await loadChart(chart, { fetch });
    expect(calls).toHaveLength(1);
    expect(calls[0]?.init?.credentials).toBe("same-origin");
    expect(new Headers(calls[0]?.init?.headers).get("Accept")).toBe("application/json");
  });

  it("lets the app set the request", async () => {
    const { chart, rows, url } = served(GOOD);
    const { fetch, calls } = fakeFetch({ [url]: rows });
    await loadChart(chart, {
      fetch,
      init: { credentials: "include", headers: { Authorization: "Bearer t" } },
    });
    expect(calls[0]?.init?.credentials).toBe("include");
    expect(new Headers(calls[0]?.init?.headers).get("Authorization")).toBe("Bearer t");
  });

  it("leaves inline rows alone", async () => {
    const { chart, rows } = served(GOOD);
    const { fetch, calls } = fakeFetch({});
    const inline = { ...chart, data: { values: rows } };
    expect(await loadChart(inline, { fetch })).toBe(inline);
    expect(calls).toHaveLength(0);
  });

  it("says the rows are gone when the route answers 404", async () => {
    const { chart } = served(GOOD);
    const error = await loadChart(chart, fakeFetch({})).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ChartRowsError);
    expect((error as ChartRowsError).status).toBe(404);
  });

  it("refuses rows that are not a list", async () => {
    const { chart, url } = served(GOOD);
    const error = await loadChart(chart, fakeFetch({ [url]: { rows: [] } })).catch((e) => e);
    expect(error).toBeInstanceOf(ChartRowsError);
    expect((error as ChartRowsError).status).toBeUndefined();
  });

  it("wraps a network failure", async () => {
    const { chart } = served(GOOD);
    const fetch = (async () => {
      throw new TypeError("Failed to fetch");
    }) as typeof globalThis.fetch;
    const error = await loadChart(chart, { fetch }).catch((e) => e);
    expect(error).toBeInstanceOf(ChartRowsError);
    expect((error as ChartRowsError).cause).toBeInstanceOf(TypeError);
  });

  it("passes an abort through", async () => {
    const { chart } = served(GOOD);
    const controller = new AbortController();
    const fetch = ((_url: string, init: RequestInit) =>
      new Promise((_resolve, reject) => {
        init.signal?.addEventListener("abort", () => reject(init.signal?.reason));
      })) as typeof globalThis.fetch;
    const pending = loadChart(chart, { fetch, signal: controller.signal });
    controller.abort();
    await expect(pending).rejects.not.toBeInstanceOf(ChartRowsError);
  });
});

describe("checkChart", () => {
  const loaded = (name: string): LoadedChart => {
    const { chart, rows } = served(name);
    return { ...chart, data: { values: rows } };
  };

  it("passes a chart that draws one mark per row", () => {
    expect(checkChart(loaded(GOOD)).errors).toEqual([]);
  });

  it("stops a chart Flint would merge rows for", () => {
    const check = checkChart(loaded(MERGED));
    expect(check.errors.length).toBeGreaterThan(0);
    expect(check.warnings.map((w) => w.code)).not.toContain("implicit-aggregate");
  });

  it("stops a chart Flint cannot assemble", () => {
    const chart = loaded(GOOD);
    const broken = { ...chart, chart_spec: { ...chart.chart_spec, chartType: "Sankey Swirl" } };
    expect(checkChart(broken).errors.length).toBeGreaterThan(0);
  });
});
