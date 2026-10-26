// The page the browser tests drive: one chart, from the Python side's Flint inputs, its rows
// served by URL (the tests answer the rows route).
import type { ChartAssemblyInput } from "flint-chart";
import { createRoot } from "react-dom/client";
import { ShowChartToolCall, SLayerChart } from "../../src/react.js";
import cases from "../../test/flint-inputs.json" with { type: "json" };

const params = new URLSearchParams(location.search);
const name = params.get("case") ?? "";
const input = (cases as unknown as Record<string, { input: ChartAssemblyInput }>)[name]?.input;
if (!input) throw new Error(`no case ${name}`);
const chart: ChartAssemblyInput = {
  ...input,
  chart_spec: { ...input.chart_spec, title: input.chart_spec.title ?? name },
  data: { url: `/flint/charts/${name}/rows` },
};
const receipt = JSON.stringify({ ok: true, chart_id: name, rows_drawn: 0, chart });

const root = document.getElementById("root");
if (!root) throw new Error("no root");
createRoot(root).render(
  params.has("tool") ? (
    <ShowChartToolCall status="complete" result={receipt} width={640} height={400} renderer="svg" />
  ) : (
    <SLayerChart
      chart={chart}
      width={640}
      height={400}
      renderer="svg"
      onRender={() => document.body.setAttribute("data-rendered", "true")}
    />
  ),
);
