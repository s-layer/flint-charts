// @vitest-environment happy-dom
import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import { cleanup, render, screen } from "@testing-library/react";
import type { ComponentType } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { showChartTool } from "../src/assistant-ui.js";
import { showChartRenderer } from "../src/copilotkit.js";
import { showChartArgs } from "../src/schema.js";
import { fakeFetch, GOOD, receipt, served } from "./fixtures.js";

afterEach(cleanup);

const { chart } = served(GOOD);
const result = JSON.stringify(receipt(chart, 6));

describe("CopilotKit", () => {
  // CopilotKit draws a renderer's `render` as a component.
  type Props = { status: string; args: object; result: string | undefined };
  const componentOf = (renderer = showChartRenderer()) =>
    renderer.render as unknown as ComponentType<Props>;

  it("draws show_chart by default", () => {
    expect(showChartRenderer().name).toBe("show_chart");
    expect(showChartRenderer({ name: "chart", agentId: "analyst" })).toMatchObject({
      name: "chart",
      agentId: "analyst",
    });
  });

  it("shows the title while the arguments stream", () => {
    const Chart = componentOf();
    render(<Chart status="inProgress" args={{ title: "Revenue" }} result={undefined} />);
    expect(screen.getByRole("status").textContent).toBe("Revenue");
  });

  it("draws the chart once the result arrives", async () => {
    const { fetch, calls } = fakeFetch({});
    const Chart = componentOf(showChartRenderer({ fetch }));
    render(<Chart status="complete" args={{ title: "Revenue" }} result={result} />);
    await screen.findByRole("alert");
    expect(calls.map((call) => call.url)).toEqual([chart.data.url]);
  });
});

describe("assistant-ui", () => {
  type Part = Partial<ToolCallMessagePartProps>;
  const componentOf = (tool = showChartTool()) => tool.render as unknown as ComponentType<Part>;

  it("is a backend tool drawn on its own", () => {
    expect(showChartTool()).toMatchObject({ type: "backend", display: "standalone" });
  });

  it("shows the title while the tool runs", () => {
    const Chart = componentOf();
    render(<Chart status={{ type: "running" }} args={{ title: "Revenue" }} argsText="" />);
    expect(screen.getByRole("status").textContent).toBe("Revenue");
  });

  it("draws the chart from the parsed result", async () => {
    const { fetch, calls } = fakeFetch({});
    const Chart = componentOf(showChartTool({ fetch }));
    render(<Chart status={{ type: "complete" }} args={{}} result={receipt(chart, 6)} />);
    await screen.findByRole("alert");
    expect(calls.map((call) => call.url)).toEqual([chart.data.url]);
  });

  it.each(["cancelled", "error"])("shows nothing for a call that ended %s", (reason) => {
    const Chart = componentOf();
    const view = render(
      <Chart status={{ type: "incomplete", reason } as never} args={{ title: "Revenue" }} />,
    );
    expect(view.container.innerHTML).toBe("");
  });

  it("waits for a preliminary result to settle", () => {
    const Chart = componentOf();
    render(<Chart status={{ type: "running" }} args={{}} result={{ ok: true }} isPreliminary />);
    expect(screen.getByRole("status")).toBeTruthy();
  });
});

describe("showChartArgs", () => {
  const validate = showChartArgs["~standard"].validate;

  it("accepts show_chart's arguments", () => {
    const args = { result_id: "r_1", chart_type: "Line Chart", encodings: {}, title: "T" };
    expect(validate(args)).toEqual({ value: args });
  });

  it("names what is missing", () => {
    const outcome = validate({ result_id: "r_1" });
    expect(outcome.issues?.map((issue) => issue.message)).toEqual([
      "chart_type must be a string",
      "title must be a string",
      "encodings must be an object",
    ]);
  });
});
