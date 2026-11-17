// Validate Flint chart inputs with flint-chart's own validateChart, for FlintSidecar.
//
// Usage: node flint_validate.mjs [expected-flint-chart-version]
//
// Protocol, one JSON object per line:
//   stdout, once at start: {"ready": true, "version": "1.1.0"}, or {"fatal": "..."} and exit 1
//   stdin:  {"id": 1, "input": <ChartAssemblyInput>}
//   stdout: {"id": 1, "result": <ValidateResult>}, or {"id": 1, "error": "..."}
// Only protocol lines go to stdout; anything else goes to stderr.
//
// flint-chart is found, in order, at FLINT_CHART_DIR, beside each node_modules/.bin on PATH
// (where `npx -p flint-chart@X node flint_validate.mjs` installs it), in node_modules next to
// this script (after `npm install` here), then in ./node_modules of the working directory.

import { existsSync, readFileSync } from "node:fs";
import { delimiter, dirname, join, resolve, sep } from "node:path";
import { createInterface } from "node:readline";
import { fileURLToPath, pathToFileURL } from "node:url";

const write = (message) => process.stdout.write(`${JSON.stringify(message)}\n`);

function candidates() {
  const dirs = [];
  if (process.env.FLINT_CHART_DIR) dirs.push(resolve(process.env.FLINT_CHART_DIR));
  for (const entry of (process.env.PATH ?? "").split(delimiter)) {
    if (entry.endsWith(`node_modules${sep}.bin`)) dirs.push(join(dirname(entry), "flint-chart"));
  }
  dirs.push(fileURLToPath(new URL("./node_modules/flint-chart", import.meta.url)));
  dirs.push(resolve("node_modules", "flint-chart"));
  return dirs;
}

async function load(expected) {
  for (const dir of candidates()) {
    const manifest = join(dir, "package.json");
    if (!existsSync(manifest)) continue;
    const pkg = JSON.parse(readFileSync(manifest, "utf8"));
    if (pkg.name !== "flint-chart") continue;
    if (expected && pkg.version !== expected) {
      throw new Error(`found flint-chart ${pkg.version} at ${dir}, expected ${expected}`);
    }
    const entry = pkg.exports?.["./validate"]?.import;
    if (typeof entry !== "string") throw new Error(`flint-chart ${pkg.version} has no ./validate`);
    const { validateChart } = await import(pathToFileURL(join(dir, entry)).href);
    return { validateChart, version: pkg.version };
  }
  throw new Error("flint-chart is not installed; run with `npx -p flint-chart@<version> node`");
}

let flint;
try {
  flint = await load(process.argv[2]);
} catch (error) {
  write({ fatal: error instanceof Error ? error.message : String(error) });
  process.exit(1);
}
write({ ready: true, version: flint.version });

for await (const line of createInterface({ input: process.stdin, crlfDelay: Infinity })) {
  if (!line.trim()) continue;
  let id = null;
  try {
    const request = JSON.parse(line);
    id = request.id ?? null;
    write({ id, result: flint.validateChart(request.input, "vegalite") });
  } catch (error) {
    write({ id, error: error instanceof Error ? error.message : String(error) });
  }
}
