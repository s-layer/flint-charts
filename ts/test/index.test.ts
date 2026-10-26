import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { VERSION } from "../src/index.js";

describe("package", () => {
  it("exports the version from package.json", () => {
    const pkg = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8")) as {
      version: string;
    };
    expect(VERSION).toBe(pkg.version);
  });
});

describe("client entry points", () => {
  // Next.js renders a module's components on the client only when the module says so.
  it.each(["react.tsx", "copilotkit.tsx", "assistant-ui.tsx"])("%s is a client module", (file) => {
    const source = readFileSync(new URL(`../src/${file}`, import.meta.url), "utf8");
    expect(source.startsWith('"use client";')).toBe(true);
  });
});
