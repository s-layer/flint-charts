import { readFileSync } from "node:fs";
import { getRegistryEntry, isRegistered, supportedInteractionPresets } from "flint-chart";
import { vlGetTemplateDef } from "flint-chart/vegalite";
import { describe, expect, it } from "vitest";

// Kept in step with the Python mapping (s_layer_flint_charts._mapping) by hand; a Python test checks it.
const pin = JSON.parse(readFileSync(new URL("./flint-pin.json", import.meta.url), "utf8")) as {
  flintVersion: string;
  flintMcpVersion: string;
  semanticTypes: string[];
  chartTypes: Record<string, string[]>;
};

const version = (name: string) =>
  (
    JSON.parse(
      readFileSync(new URL(`../node_modules/${name}/package.json`, import.meta.url), "utf8"),
    ) as { version: string }
  ).version;

const TIME_AXIS = ["Date", "DateTime", "Year", "YearMonth", "YearQuarter"];

describe("Python mapping pin", () => {
  it("names the flint-chart version installed here", () => {
    expect(version("flint-chart")).toBe(pin.flintVersion);
  });

  it("names the flint-chart-mcp version installed here", () => {
    expect(version("flint-chart-mcp")).toBe(pin.flintMcpVersion);
  });

  it.each(pin.semanticTypes)("%s is a registered Flint semantic type", (semanticType) => {
    expect(isRegistered(semanticType)).toBe(true);
  });

  it.each(TIME_AXIS)("%s is a point on a timeline, not a cycle", (semanticType) => {
    expect(pin.semanticTypes).toContain(semanticType);
    const entry = getRegistryEntry(semanticType);
    expect(entry.visEncodings).toContain("temporal");
    expect(entry.domainShape).not.toBe("cyclic");
  });

  it("never emits a cyclic type", () => {
    const cyclic = pin.semanticTypes.filter(
      (semanticType) => getRegistryEntry(semanticType).domainShape === "cyclic",
    );
    expect(cyclic).toEqual([]);
  });

  it.each([
    "Amount",
    "Price",
    "Count",
    "Number",
    "Percentage",
    "PercentageChange",
    "Duration",
    "Quantity",
  ])("%s is drawn as a quantity", (semanticType) => {
    expect(getRegistryEntry(semanticType).visEncodings).toContain("quantitative");
  });

  it("splits currency by aggregation role: Amount sums, Price averages", () => {
    expect(getRegistryEntry("Amount").aggRole).toBe("additive");
    expect(getRegistryEntry("Price").aggRole).toBe("intensive");
    expect(getRegistryEntry("Amount").formatClass).toBe("currency");
    expect(getRegistryEntry("Price").formatClass).toBe("currency");
  });
});

describe("chart types show_chart draws", () => {
  it.each(Object.entries(pin.chartTypes))(
    "%s is a Vega-Lite chart that supports its default interactions",
    (chartType, presets) => {
      const template = vlGetTemplateDef(chartType);
      expect(template).toBeDefined();
      expect(supportedInteractionPresets(template?.interactionSupport)).toEqual(
        expect.arrayContaining(presets),
      );
    },
  );
});
