// @vitest-environment happy-dom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { SLayerChart } from "../src/react.js";
import { fakeFetch, GOOD, served } from "./fixtures.js";

// Flint throwing while it checks a chart, as it may for an input of an unexpected shape.
vi.mock("flint-chart/validate", () => ({
  validateChart: () => {
    throw new TypeError("cannot read encodings");
  },
}));

afterEach(cleanup);

it("shows the error note when Flint throws while checking the chart", async () => {
  const { chart, rows, url } = served(GOOD);
  render(<SLayerChart chart={chart} fetch={fakeFetch({ [url]: rows }).fetch} />);
  expect((await screen.findByRole("alert")).textContent).toBe("This chart could not be drawn.");
});
