import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, type Page, test } from "@playwright/test";

type Case = { input: { data: { values: unknown[] } }; problems: string[] };
const cases: Record<string, Case> = JSON.parse(
  readFileSync(join(import.meta.dirname, "../test/flint-inputs.json"), "utf8"),
);
const guarded = Object.keys(cases).filter((name) => cases[name]?.problems.length === 0);
const merged = Object.keys(cases).filter((name) => (cases[name]?.problems.length ?? 0) > 0);

/** Answer the rows route as the Python server would, and note each request. */
async function serveRows(page: Page, status = 200) {
  const requests: { url: string; accept: string | undefined }[] = [];
  await page.route("**/flint/charts/*/rows", async (route) => {
    const url = new URL(route.request().url());
    requests.push({ url: url.pathname, accept: route.request().headers().accept });
    const name = url.pathname.split("/")[3] ?? "";
    await route.fulfill({ status, json: status === 200 ? cases[name]?.input.data.values : {} });
  });
  return requests;
}

/** The chart's errors in the browser console, which a broken chart would log. */
function consoleErrors(page: Page) {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  return errors;
}

for (const name of guarded) {
  test(`draws ${name} from the rows its URL serves`, async ({ page }) => {
    const errors = consoleErrors(page);
    const requests = await serveRows(page);
    await page.goto(`/?case=${name}`);
    await expect(page.locator("body")).toHaveAttribute("data-rendered", "true");
    const svg = page.locator("#root svg").first();
    await expect(svg).toBeVisible();
    expect(await page.locator("#root svg [role=graphics-symbol]").count()).toBeGreaterThan(0);
    await expect(page.getByRole("alert")).toHaveCount(0);
    expect(requests).toEqual([{ url: `/flint/charts/${name}/rows`, accept: "application/json" }]);
    expect(errors).toEqual([]);
  });
}

test("draws one bar per row", async ({ page }) => {
  await serveRows(page);
  await page.goto("/?case=growth_bars");
  await expect(page.locator("body")).toHaveAttribute("data-rendered", "true");
  await expect(page.locator("#root svg .mark-rect [role=graphics-symbol]")).toHaveCount(
    cases.growth_bars?.input.data.values.length ?? -1,
  );
});

for (const name of merged) {
  test(`refuses ${name}, which Flint would merge rows for`, async ({ page }) => {
    await serveRows(page);
    await page.goto(`/?case=${name}`);
    await expect(page.getByRole("alert")).toHaveText("This chart could not be drawn.");
    await expect(page.locator("#root svg")).toHaveCount(0);
  });
}

test("shows the title in a busy box until the rows arrive", async ({ page }) => {
  const name = guarded[0] ?? "";
  let release = () => {};
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/flint/charts/*/rows", async (route) => {
    await held;
    await route.fulfill({ json: cases[name]?.input.data.values });
  });
  await page.goto(`/?case=${name}`);
  await expect(page.getByRole("status")).toHaveAttribute("aria-busy", "true");
  release();
  await expect(page.locator("body")).toHaveAttribute("data-rendered", "true");
  await expect(page.getByRole("status")).toHaveCount(0);
});

test("says the data expired when the rows route answers 404", async ({ page }) => {
  await serveRows(page, 404);
  await page.goto(`/?case=${guarded[0]}`);
  await expect(page.getByRole("alert")).toHaveText(
    "This chart's data has expired. Ask for it again to redraw it.",
  );
});

test("draws a show_chart result", async ({ page }) => {
  const requests = await serveRows(page);
  await page.goto(`/?case=${guarded[0]}&tool`);
  await expect(page.locator("#root svg").first()).toBeVisible();
  expect(requests).toHaveLength(1);
});
