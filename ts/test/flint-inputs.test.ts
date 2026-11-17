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
  percent_fields: string[];
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

// The rows hold percentages as fractions and the annotation says so (percentScale). Flint reads
// them as fractions, including a column it would otherwise guess was percent points.
const percentFields = Object.entries(cases).flatMap(([name, c]) =>
  c.percent_fields.map((field) => [`${name}.${field}`, c, field] as const),
);

const tooltip = (c: Case, field: string, annotation = c.input.semantic_types?.[field]) => {
  const normalized = normalizeAnnotation(annotation);
  const values = (c.input.data.values as Record<string, unknown>[]).map((row) => row[field]);
  return resolveFormat(normalized.semanticType, normalized, values).tooltipFormat;
};

describe("percentages", () => {
  it("state that they hold fractions", () => {
    expect(percentFields.length).toBeGreaterThan(0);
    for (const [, c, field] of percentFields) {
      expect(normalizeAnnotation(c.input.semantic_types?.[field]).percentScale).toBe("fraction");
    }
  });

  it.each(percentFields)("%s is read as fractions", (_name, c, field) => {
    const format = tooltip(c, field);
    expect(format?.pattern).toMatch(/%$/);
    expect(format?.suffix).toBeUndefined();
  });

  it("include one Flint would read as percent points if not told", () => {
    const misread = percentFields.filter(([, c, field]) => {
      const { percentScale: _, ...unstated } = normalizeAnnotation(c.input.semantic_types?.[field]);
      return tooltip(c, field, unstated)?.suffix === "%";
    });
    expect(misread.map(([name]) => name)).toContain("growth_bars.growth");
  });
});
