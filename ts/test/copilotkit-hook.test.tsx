// @vitest-environment happy-dom
import { cleanup, render, screen } from "@testing-library/react";
import type { ComponentType } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { useShowChartRenderer } from "../src/copilotkit.js";

type Props = { status: string; parameters: object; result: string | undefined };
const registered: { name: string; render: ComponentType<Props> }[] = [];

let lastDeps: readonly unknown[] | undefined;

// Register again only when the deps change, as CopilotKit's hook does.
vi.mock("@copilotkit/react-core/v2", () => ({
  defineToolCallRenderer: (def: unknown) => def,
  useRenderTool: (
    config: { name: string; render: ComponentType<Props> },
    deps: readonly unknown[] = [],
  ) => {
    if (lastDeps && deps.length === lastDeps.length && deps.every((d, i) => d === lastDeps?.[i])) {
      return;
    }
    lastDeps = deps;
    registered.push(config);
  },
}));

afterEach(cleanup);

function Host({ width }: { width: number }) {
  useShowChartRenderer({ width });
  return null;
}

it("draws calls with the options of the latest render", () => {
  const host = render(<Host width={300} />);
  host.rerender(<Host width={500} />);
  const Chart = registered.at(-1)?.render;
  if (!Chart) throw new Error("nothing registered");
  render(<Chart status="inProgress" parameters={{ title: "Revenue" }} result={undefined} />);
  expect(screen.getByRole("status").style.width).toBe("500px");
});
