import { readFileSync } from "node:fs";
import {
  type ChartAssemblyInput,
  normalizeAnnotation,
  resolveFormat,
  validateChart,
} from "flint-chart";
import { describe, expect, it } from "vitest";

// Flint inputs the Python side builds from query results (tests/test_flint_inputs.py writes
// this file and checks it is current).
type Case = {
  input: ChartAssemblyInput;
  problems: string[];
  percent_forms: Record<string, "fraction" | "points">;
};
const cases: Record<string, Case> = JSON.parse(
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

// Flint guesses whether a percentage holds fractions or points from its values; the server
// sends each one in the form Flint will read it as (percent_points in _mapping.py).
const percentFields = Object.entries(cases).flatMap(([name, c]) =>
  Object.entries(c.percent_forms).map(
    ([field, form]) => [`${name}.${field}`, c, field, form] as const,
  ),
);

describe("percentages", () => {
  it("cover both forms", () => {
    expect(new Set(percentFields.map(([, , , form]) => form))).toEqual(
      new Set(["fraction", "points"]),
    );
  });

  it.each(percentFields)("%s is read in the form it is sent", (_name, c, field, form) => {
    const annotation = normalizeAnnotation(c.input.semantic_types?.[field]);
    const values = (c.input.data.values as Record<string, unknown>[]).map((row) => row[field]);
    const { tooltipFormat } = resolveFormat(annotation.semanticType, annotation, values);
    if (form === "points") {
      expect(tooltipFormat?.suffix).toBe("%");
    } else {
      expect(tooltipFormat?.pattern).toMatch(/%$/);
    }
  });
});
