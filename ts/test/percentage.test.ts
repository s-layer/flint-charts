import { resolveColorSchemeHint, resolveDomainConstraint, resolveFormat } from "flint-chart";
import { describe, expect, it } from "vitest";

// The annotations the Python mapping emits for a percentage block, before and after
// fit_to_values (tests/test_mapping.py::TestFitToValues pins the same shapes).
const share = { semanticType: "Percentage", intrinsicDomain: [0, 1] as [number, number] };
const fitted = (low: number, high: number) => ({
  semanticType: "PercentageChange",
  intrinsicDomain: [Math.min(0, low), Math.max(1, high)] as [number, number],
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
});
