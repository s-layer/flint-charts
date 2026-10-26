import { readFileSync } from "node:fs";
import { type ChartAssemblyInput, validateChart } from "flint-chart";
import { describe, expect, it } from "vitest";

// Flint inputs the Python side builds from query results (tests/test_flint_inputs.py writes
// this file and checks it is current).
const cases: Record<string, { input: ChartAssemblyInput; problems: string[] }> = JSON.parse(
  readFileSync(new URL("./flint-inputs.json", import.meta.url), "utf8"),
);
const guarded = Object.entries(cases).filter(([, c]) => c.problems.length === 0);
const refused = Object.entries(cases).filter(([, c]) => c.problems.length > 0);

const codes = (input: ChartAssemblyInput) =>
  validateChart(input, "vegalite").warnings.map((w) => w.code);

describe("charts the grain guard passes", () => {
  it.each(guarded)("%s assembles cleanly", (_name, { input }) => {
    const result = validateChart(input, "vegalite");
    expect(result.errors).toEqual([]);
    expect(result.valid).toBe(true);
  });

  it.each(guarded)("%s draws one mark per row", (_name, { input }) => {
    expect(codes(input)).not.toContain("implicit-aggregate");
  });

  it.each(guarded)("%s uses only registered types", (_name, { input }) => {
    expect(codes(input)).not.toContain("unknown_semantic_type");
  });
});

describe("charts the grain guard refuses", () => {
  it("covers at least one case", () => {
    expect(refused.length).toBeGreaterThan(0);
  });

  it.each(refused)("%s is one Flint would merge rows for", (_name, { input }) => {
    expect(codes(input)).toContain("implicit-aggregate");
  });
});
