// @vitest-environment happy-dom
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ChartRowsError } from "../src/index.js";
import { describeError, ShowChartToolCall, SLayerChart } from "../src/react.js";
import { fakeFetch, GOOD, MERGED, receipt, served } from "./fixtures.js";

afterEach(cleanup);

/** A `fetch` whose answer waits until `release` is called. */
function heldFetch(rows: unknown) {
  let release = () => {};
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  const calls: string[] = [];
  const fetch = (async (input: RequestInfo | URL) => {
    calls.push(String(input));
    await held;
    return new Response(JSON.stringify(rows));
  }) as typeof globalThis.fetch;
  return { fetch, calls, release };
}

describe("SLayerChart", () => {
  it("shows the title in a busy box while the rows load", async () => {
    const { chart: untitled, rows } = served(GOOD);
    const chart = {
      ...untitled,
      chart_spec: { ...untitled.chart_spec, title: "Margin by quarter" },
    };
    const { fetch, release } = heldFetch(rows);
    render(<SLayerChart chart={chart} fetch={fetch} />);
    const box = screen.getByRole("status");
    expect(box.getAttribute("aria-busy")).toBe("true");
    expect(box.textContent).toBe("Margin by quarter");
    await act(async () => release());
  });

  it("says the data expired when the rows route answers 404", async () => {
    const { chart } = served(GOOD);
    render(<SLayerChart chart={chart} fetch={fakeFetch({}).fetch} />);
    expect((await screen.findByRole("alert")).textContent).toMatch(/expired/);
  });

  it("refuses a chart Flint would merge rows for", async () => {
    const { chart, rows, url } = served(MERGED);
    render(<SLayerChart chart={chart} fetch={fakeFetch({ [url]: rows }).fetch} />);
    expect((await screen.findByRole("alert")).textContent).toBe("This chart could not be drawn.");
  });

  it("lets the app draw its own error", async () => {
    const { chart } = served(GOOD);
    render(
      <SLayerChart
        chart={chart}
        fetch={fakeFetch({}).fetch}
        renderError={(error) => <p role="alert">{(error as ChartRowsError).status}</p>}
      />,
    );
    expect((await screen.findByRole("alert")).textContent).toBe("404");
  });

  it("fetches once while the chart keeps its URL", async () => {
    const { chart, rows, url } = served(MERGED);
    const { fetch, calls } = fakeFetch({ [url]: rows });
    const view = render(<SLayerChart chart={chart} fetch={fetch} />);
    await screen.findByRole("alert");
    // A tool-call view parses its result afresh on each render.
    view.rerender(<SLayerChart chart={structuredClone(chart)} fetch={fetch} />);
    view.rerender(<SLayerChart chart={structuredClone(chart)} fetch={fetch} />);
    await screen.findByRole("alert");
    expect(calls.map((call) => call.url)).toEqual([url]);
  });

  it("fetches again for a new chart", async () => {
    const first = served(MERGED);
    const second = served(MERGED, "/flint/charts/c_2/rows");
    const { fetch, calls } = fakeFetch({ [first.url]: first.rows, [second.url]: second.rows });
    const view = render(<SLayerChart chart={first.chart} fetch={fetch} />);
    await screen.findByRole("alert");
    view.rerender(<SLayerChart chart={second.chart} fetch={fetch} />);
    await waitFor(() => expect(calls).toHaveLength(2));
    expect(calls.map((call) => call.url)).toEqual([first.url, second.url]);
  });
});

describe("ShowChartToolCall", () => {
  it("shows the title while the model writes the call", () => {
    render(<ShowChartToolCall status="streaming" args={{ title: "Revenue by month" }} />);
    expect(screen.getByRole("status").textContent).toBe("Revenue by month");
  });

  it("shows a busy box before the title arrives", () => {
    render(<ShowChartToolCall status="running" args={{}} />);
    expect(screen.getByRole("status").getAttribute("aria-label")).toBe("Drawing a chart");
  });

  it("shows nothing for a chart the server refused", () => {
    const view = render(
      <ShowChartToolCall status="complete" result="The chart was not drawn:\n- fix it" />,
    );
    expect(view.container.innerHTML).toBe("");
  });

  it("draws the chart the receipt holds", async () => {
    const { chart } = served(GOOD);
    const { fetch, calls } = fakeFetch({});
    render(
      <ShowChartToolCall
        status="complete"
        result={JSON.stringify(receipt(chart, 6))}
        fetch={fetch}
      />,
    );
    expect((await screen.findByRole("alert")).textContent).toMatch(/expired/);
    expect(calls.map((call) => call.url)).toEqual([chart.data.url]);
  });
});

describe("describeError", () => {
  it.each([
    [new ChartRowsError("gone", { status: 404 }), /expired/],
    [new ChartRowsError("down", { status: 500 }), /could not be loaded/],
    [new Error("boom"), /could not be drawn/],
  ])("words %s for a reader", (error, words) => {
    expect(describeError(error)).toMatch(words);
  });
});
