import { resolveColorSchemeHint, resolveDomainConstraint, resolveFormat } from "flint-chart";
import { describe, expect, it } from "vitest";

// The annotations the Python mapping emits for a percentage block, before and after
// fit_to_values (tests/test_mapping.py::TestFitToValues pins the same shapes).
const share = {
  semanticType: "Percentage",
  intrinsicDomain: [0, 1] as [number, number],
  percentScale: "fraction" as const,
};
const fitted = (low: number, high: number) => ({
  semanticType: "PercentageChange",
  intrinsicDomain: [Math.min(0, low), Math.max(1, high)] as [number, number],
  percentScale: "fraction" as const,
});

describe("percentages in Flint", () => {
  it("formats a share as a percentage", () => {
    const values = [0.12, 0.34, 0.5];
    expect(resolveFormat(share.semanticType, share, values).format?.pattern).toMatch(/%$/);
  });

  it("formats a fitted change as a percentage", () => {
    const values = [-0.12, 0.3, 0.45];
    const annotation = fitted(-0.12, 0.45);
    expect(resolveFormat(annotation.semanticType, annotation, values).format?.pattern).toMatch(
      /%$/,
    );
  });

  it("pivots a fitted change that crosses zero on zero", () => {
    const values = [-0.12, 0.3, 1.8];
    const annotation = fitted(-0.12, 1.8);
    expect(resolveColorSchemeHint(annotation.semanticType, annotation, values)).toMatchObject({
      type: "diverging",
      divergingMidpoint: 0,
    });
  });

  it("would pivot the same values on 0.5 left as a share", () => {
    // Why fit_to_values exists: the [0, 1] domain's centre is the pivot.
    const values = [-0.12, 0.3, 1.8];
    expect(resolveColorSchemeHint(share.semanticType, share, values)).toMatchObject({
      type: "diverging",
      divergingMidpoint: 0.5,
    });
  });

  it("keeps an all-positive fitted change sequential", () => {
    const values = [0.2, 1.1, 2.5];
    const annotation = fitted(0.2, 2.5);
    expect(resolveColorSchemeHint(annotation.semanticType, annotation, values).type).toBe(
      "sequential",
    );
  });

  it("never clamps a fitted change inside its values", () => {
    const values = [-0.12, 0.3, 1.8];
    const annotation = fitted(-0.12, 1.8);
    const domain = resolveDomainConstraint(annotation.semanticType, annotation, values);
    expect(domain?.min ?? -Infinity).toBeLessThanOrEqual(-0.12);
    expect(domain?.max ?? Infinity).toBeGreaterThanOrEqual(1.8);
  });

  // flint-chart#154: growth stored as fractions, mostly past 100%.
  const growth = [0.5, 1.8, 2.4, 3.0, 1.2];

  it("reads growth mostly past 100% as fractions when told", () => {
    const annotation = fitted(0.5, 3.0);
    const { format, tooltipFormat } = resolveFormat(annotation.semanticType, annotation, growth);
    expect(format?.pattern).toMatch(/%$/);
    expect(tooltipFormat?.pattern).toMatch(/%$/);
    expect(tooltipFormat?.suffix).toBeUndefined();
  });

  it("would read the same growth as percent points if not told", () => {
    // Why the mapping sends percentScale: the fitted domain [0, 3] does not settle the scale.
    const { percentScale: _, ...unstated } = fitted(0.5, 3.0);
    expect(resolveFormat(unstated.semanticType, unstated, growth).tooltipFormat).toMatchObject({
      suffix: "%",
    });
  });

  it("formats one column one way whichever rows a query returns", () => {
    const annotation = fitted(0.2, 3.0);
    const mostlyBelow = [0.5, 0.8, 0.4, 3.0, 0.2];
    expect(resolveFormat(annotation.semanticType, annotation, mostlyBelow)).toEqual(
      resolveFormat(annotation.semanticType, annotation, growth),
    );
  });

  it("keeps a domain that reaches past 1 from clamping growth", () => {
    const annotation = fitted(0.5, 3.0);
    const domain = resolveDomainConstraint(annotation.semanticType, annotation, growth);
    expect(domain?.max ?? Infinity).toBeGreaterThanOrEqual(3.0);
  });
});
