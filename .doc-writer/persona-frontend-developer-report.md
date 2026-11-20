# Persona Report

**Generated:** 2026-11-20
**Audience:** Frontend developer (advanced)
**Scenarios tested:** 7 (one per `user_tasks` entry)
**Results:** 4 PASS, 3 PARTIAL, 0 FAIL

Method: each scenario was walked using only the docs (`README.md`, `ts/README.md`,
`docs/*.md`, `docs/index.rst`), following links and the sidebar toctree. Each conclusion was
then checked against `ts/src/` (and, for rows-route claims, `src/s_layer_flint_charts/`
`server.py`, `_store.py`, `_charts.py`, `pydantic_ai.py`), the installed `flint-chart@1.1.0`
type definitions and `ts/package.json`. A verdict reflects whether the docs are *right*, not only
whether they read well.

## Summary

The chat-UI path is strong. `chat-ui.md` and `typescript.md` give copy-ready CopilotKit,
assistant-ui and plain-React setups. They match the source, and the reader-facing messages
match `describeError` word for word. The gaps are all at the edges. Release notes for the 0.3.0
dependency change are missing (the changelog page includes a `CHANGELOG.md` that does not
exist). The docs never state which `flint-chart` version is pinned, though the no-React example
tells you to install `flint-chart` yourself. The cross-origin CORS instructions leave out the
`Authorization` header. And a custom `loading` box cannot show the chart's title, which the docs
do not say. One source bug: `VERSION` is still `"0.1.0"` while `package.json` says `0.2.0`.

---

## Scenario S1: Install the package and its peers (including the upgrade from 0.2.0)

**Verdict:** PARTIAL

### Navigation Path

1. Started at: `README.md` (root)
   - Found: two packages listed; `@s-layer/flint-charts (TypeScript, ts/)`. Only `pip install`
     is shown. No npm command, no link to the docs site or to `ts/README.md`.
   - Followed: sidebar (docs site) → `docs/index.rst`.
2. Navigated to: `docs/index.rst`
   - Found: Python install and quick start only. "…and :doc:`chat-ui` to draw those charts in
     a chat."
   - Followed: link to `chat-ui`.
3. Navigated to: `docs/chat-ui.md` (top)
   - Found: `npm install @s-layer/flint-charts`. "Flint brings the chart libraries it draws with
     (Vega-Lite among them). The package needs React 18 or later." There is a `"use client"` note
     for Next.js.
   - Friction: no CopilotKit or assistant-ui version ranges here. "Flint" is used without saying
     what it is or linking it (a `never_assume` item). `ts/README.md` does link it.
4. Navigated to: `docs/typescript.md` (entry-point table)
   - Found: `@copilotkit/react-core` 1.80+, `@assistant-ui/react` 0.15, React 18+. The core
     entry "Needs: nothing beyond `flint-chart`".
   - Friction: "nothing beyond `flint-chart`" reads as if I must install `flint-chart`. The
     `checkChart` example says "install `flint-chart` and `vega-embed` as your own dependencies",
     with no version.
5. Navigated to: `docs/changelog.md` (Release notes, for the 0.2.0 → 0.3.0 upgrade)
   - Found: an intro paragraph and an `{include} ../CHANGELOG.md`.
   - Dead end: there is no `CHANGELOG.md` anywhere in the repository, so the page has no notes.
     Nothing tells me that vega, vega-lite and vega-tooltip are no longer peers, or that Flint is
     now pinned to 1.1.0.

### Source check

- `ts/package.json`: `dependencies: { "flint-chart": "1.1.0" }`, an exact pin installed for
  you. `peerDependencies`: `react >=18`, `@copilotkit/react-core ^1.80.0` and
  `@assistant-ui/react ^0.15.0`, all marked optional. There is no vega peer. So the docs'
  version ranges are right.
- `flint-chart@1.1.0` `dependencies` include `vega`, `vega-lite`, `vega-tooltip`, `echarts`,
  `chart.js` and `plotly.js-dist-min`. It does **not** include `vega-embed`. "Flint brings the
  chart libraries it draws with" is correct, and so is telling no-React users to install
  `vega-embed`.
- `mapping.md` (a Python page) says percentages now carry `percentScale: "fraction"` and that
  the related Flint bug was "fixed in Flint 1.1.0". A frontend developer who follows the
  `checkChart` example and runs `npm install flint-chart` gets whatever the latest version is.
  That means a second copy beside the pinned 1.1.0, or an older Flint if their lockfile already
  had one, and an older Flint guesses the percent scale. No frontend page says "1.1.0".
- Not verifiable offline: `vega-embed` usually declares `vega`/`vega-lite` as peers. Under pnpm's
  strict layout, the no-React example may then also need those two installed at top level,
  which is the opposite of the "no longer peers" message. Worth confirming before 0.3.0.

### Gap Analysis

**Where:** `docs/changelog.md` (whole page). `docs/chat-ui.md` > intro install block.
`docs/typescript.md` > entry-point table and `checkChart(chart)`. `README.md` (root).
**What:**
1. The release notes page includes a `CHANGELOG.md` that does not exist, so it has no upgrade
   notes at all.
2. No frontend page states that `flint-chart` is a dependency pinned exactly to 1.1.0, or that
   vega/vega-lite/vega-tooltip can be removed from an app's `package.json`.
3. The no-React example tells readers to install `flint-chart` with no version.
4. Peer version ranges are only in the reference table, not where you install.
5. `chat-ui.md` never says what Flint is.
6. The root README has no npm command and no link to the docs or `ts/README.md`.
**Impact:** A fresh install still works, because npm pulls Flint in. Someone upgrading from
0.2.0 gets no guidance. The no-React path can end up with two Flint versions, or one that
mishandles `percentScale`.
**Suggested Fix:**
- Add `CHANGELOG.md` with a 0.3.0 entry for the npm package: "flint-chart 1.1.0 is now a
  dependency, pinned exactly. vega, vega-lite and vega-tooltip are no longer peers, so remove
  them unless you use them yourself. Percentages carry `percentScale: "fraction"`."
- In `docs/chat-ui.md`, intro: add one sentence saying Flint is Microsoft's semantic charting
  library, with a link. Say it is installed with the package at exactly 1.1.0, and list the
  optional peers (CopilotKit 1.80+, assistant-ui 0.15) next to the npm command.
- In `docs/typescript.md`, entry-point table: change "nothing beyond `flint-chart`" to
  "nothing (installs `flint-chart` 1.1.0)". In the `checkChart` example, say
  `npm install flint-chart@1.1.0 vega-embed`, matching the pinned version.
- In `README.md` (root): add the `npm install @s-layer/flint-charts` line in its own block and a
  link to the docs site.

---

## Scenario S2: Draw show_chart calls in CopilotKit

**Verdict:** PASS

### Navigation Path

1. Started at: `README.md` → sidebar → `docs/index.rst` → `docs/chat-ui.md` > CopilotKit.
   - Found: a complete `CopilotKitProvider` example with
     `renderToolCalls={[showChartRenderer()]}`, and a link to `useShowChartRenderer()`.
2. Followed: `typescript.md#useshowchartrendereroptions` and `#showchartrendereroptions`.
   - Found: the `name` and `agentId` options, all `<ShowChartToolCall>` props, an example with
     `height`, and an explanation that options from the hook's latest render apply.

### Source check

`ts/src/copilotkit.tsx` wraps `defineToolCallRenderer` and `useRenderTool` from
`@copilotkit/react-core/v2`. The default name is `SHOW_CHART_TOOL` (`"show_chart"`). It maps
`inProgress → streaming`, `executing → running` and `complete → complete`, and `agentId` is
passed through. The docs are accurate, and so is the note that new `requestInit`/`fetch` only
apply to charts not yet fetched (`useChart` is keyed on `data.url`). `CopilotKitProvider`,
`CopilotChat`, `defineToolCallRenderer` and `useRenderTool` exist in the installed 1.87.1.

---

## Scenario S3: Draw show_chart calls in assistant-ui

**Verdict:** PASS

### Navigation Path

1. `docs/chat-ui.md` > assistant-ui: `defineToolkit({ show_chart: showChartTool() })`, then
   `AuiConfig({ tools: Tools({ toolkit }) })` on `AssistantRuntimeProvider`'s `config`.
   `ts/README.md` has the same thing in one block.
2. `typescript.md#showcharttooloptions`: it is a backend tool with `display: "standalone"`,
   the name is its toolkit key, and cancelled or failed calls show nothing.

### Source check

`ts/src/assistant-ui.tsx` returns `{ type: "backend", display: "standalone", render }`. A part
with `status.type === "incomplete"` is treated as complete with no result, so it renders
nothing. A preliminary result keeps the loading box. `AuiConfig` is a callable
(`@assistant-ui/store` `declare const AuiConfig: (config) => AuiConfig`), and `Tools` and
`defineToolkit` are exported from `@assistant-ui/react` 0.15.36. The docs match.

---

## Scenario S4: Draw a chart from a tool result in plain React

**Verdict:** PASS

### Navigation Path

1. `docs/chat-ui.md` > Any other UI: `parseReceipt` + `<SLayerChart chart={receipt.chart}>`.
   It explains that a refused chart gives `null` and why the chat shows nothing.
2. `typescript.md#parsereceiptresult`, `#chartreceipt`, `#slayerchart`, `#showcharttoolcall`
   and `#toolcallstatus`: field tables, every `<FlintChart>` prop passing through, and "rows
   fetched once per `data.url`".

### Source check

`parseReceipt` accepts JSON text or an object and requires `ok === true`, a string `chart_id`,
and `chart.data`/`chart.chart_spec` objects; anything else gives `null`. The Python side never
actually sends `{"ok": false…}` through the toolset: `pydantic_ai.py` raises `ModelRetry`
instead. Both are covered by "the retry text the model receives". `ChartReceipt` fields match
`_charts.ChartReceipt.to_dict()`, where `warnings` is present only when non-empty. Small note,
not a gap: `<SLayerChart>` passes `backend` through to `<FlintChart>`, but `checkChart` always
validates as Vega-Lite. The docs say "as Flint's Vega-Lite backend would draw it", so they are
not wrong.

---

## Scenario S5: Send credentials or headers with the rows request

**Verdict:** PARTIAL

### Navigation Path

1. `docs/chat-ui.md` > Reach the rows route: covers same-origin (proxy `/flint`) and another
   origin. For another origin you set an absolute `url_prefix`, allow the page's origin in CORS
   "with credentials allowed", use `credentials: "include"` and `SameSite=None; Secure`.
2. `docs/chat-ui.md` > Send credentials or headers: a `requestInit` example with
   `credentials: "include"` and `Authorization: Bearer …`. `fetch` replaces the global fetch.
3. `typescript.md#loadchartchart-options`: `init` is spread over
   `{ credentials: "same-origin" }`, and `Accept` is added.
4. `typescript.md#useshowchartrendereroptions`: covers a changing token in CopilotKit.

### Source check

- `loadChart` does `{ credentials: "same-origin", ...options.init }` and adds `Accept`. The docs
  are accurate. `requestInit` exists on `SLayerChartProps` (via `UseChartOptions`), so it works
  on every adapter.
- An absolute `url_prefix` works: `chart_rows_url` uses `f"{prefix.rstrip('/')}/charts/{id}/rows"`.
- The rows route (`server.py`) is a plain `GET` with no CORS handling of its own. On another
  origin, the documented example's `Authorization` header makes the browser send a preflight. A
  CORS setup that only allows the origin and credentials (Starlette's `CORSMiddleware` allows no
  extra headers by default) rejects that preflight, so every chart shows "could not be loaded".
- assistant-ui has no hook counterpart to `useShowChartRenderer`. `showChartTool(options)` is
  fixed when the toolkit is defined, so a rotating token needs a `fetch` closure. The docs do
  not say this.

### Gap Analysis

**Where:** `docs/chat-ui.md` > Reach the rows route ("Another origin") and > Send credentials or
headers with the rows request.
**What:** The cross-origin instructions don't say that CORS must also allow any header you add
(for example `allow_headers=["Authorization"]`). That is exactly the header the example on the
same page adds. There is also no guidance on a token that changes over time in assistant-ui.
**Impact:** Someone who follows both sections as written, cross-origin with a Bearer header,
gets a failed preflight and the "This chart's data could not be loaded." note on every chart.
It can be worked out, but only by debugging.
**Suggested Fix:** In `docs/chat-ui.md`, section "Reach the rows route", "Another origin"
bullet: add "and any header you add, such as `Authorization`, to its allowed headers". In
section "Send credentials or headers…", add one line: "In assistant-ui the options are fixed
when you define the toolkit. For a token that changes, pass a `fetch` that reads the current
token." Include a three-line example.

---

## Scenario S6: Style or replace the loading box and the error note

**Verdict:** PARTIAL

### Navigation Path

1. `docs/chat-ui.md` > Change the loading box and the error note: `loading` (by default a box
   with the chart's title) and `renderError`. The defaults set styles inline, "so to restyle
   them pass your own". The classes `slayer-chart-skeleton` and `slayer-chart-error` are "for
   selecting them, such as in tests". `describeError` gives the default text.
2. `typescript.md#slayerchart`: `loading: ReactNode`, also used while Flint mounts.
   `renderError: (error: Error) => ReactNode`. `#chartskeleton` and `#charterrornote` take
   `title`/`error` and a `style` prop. `#describeerrorerror` has an example.

### Source check

- `renderError` gets the `Error`, so a custom error note can use `describeError` or the
  error's `status`/`problems`. The docs are complete here.
- `loading` is a static `ReactNode` (`react.tsx` lines 108 and 147–152). The default skeleton
  gets `chart.chart_spec.title` (or `args.title` while the call streams) and a `width`/`height`
  box. A custom `loading` gets neither. Through an adapter, one `loading` node is shared by every
  `show_chart` call, so **a replacement loading box cannot show each chart's title, and it is not
  sized to `width`/`height`**. The docs say the default shows the title but never say a
  replacement can't. The only ways to restyle and keep the title are CSS that overrides the
  inline styles (`!important`), which the docs discourage, or your own tool-call renderer around
  `<ShowChartToolCall>`, which isn't shown anywhere.

### Gap Analysis

**Where:** `docs/chat-ui.md` > Change the loading box and the error note. `docs/typescript.md` >
`<SLayerChart>` (`loading` row).
**What:** It is not documented that `loading` is the same node for every chart. It does not get
the title or the box size. There is also no recipe for a branded loading box that keeps the
title.
**Impact:** Replacing the box is easy. Matching the design system *and* keeping the title,
which is the default's main point, means reading source or trying things out.
**Suggested Fix:** In `docs/chat-ui.md`, section "Change the loading box…", say: "`loading` is
one node for every chart, so it doesn't receive the title or size. To keep them, restyle the
default with `<ChartSkeleton style={…}>` inside your own tool-call view, or override the inline
styles with CSS." Then show a short example. You could also make `loading` accept
`(title?: string) => ReactNode`, which is an API change for the maintainers to decide.

---

## Scenario S7: Understand what a reader sees when a chart can't be drawn

**Verdict:** PASS

### Navigation Path

1. `docs/chat-ui.md` > What the reader sees when a chart can't be drawn: four cases with quoted
   text, the 404 causes (expired, or missing conversation), the store defaults (50 charts, one
   hour after last agent use, 1,000 conversations) and "drawing doesn't count as a use". It links
   to `agents.md#limits`.
2. `typescript.md#describeerrorerror`: the same three messages in a table.
3. `chat-ui.md` > Any other UI and `typescript.md#showcharttooloptions`: refused or cancelled
   calls show nothing.

### Source check

- The three strings match `describeError` in `react.tsx` lines 194–198 exactly, which satisfies
  the project rule.
- The 404 causes match `server.py`, which returns 404 when the session is missing or unknown or
  the chart is not in it. The defaults match `_store.py`: `ttl=3600`, `max_sessions=1000`,
  `max_charts=50`. `store.get()` doesn't refresh last-use, but `store.session()` (the tools)
  does, so "drawing a chart does not count as a use" is correct.
- A Flint mount failure showing Flint's muted box, with `onError` called, matches the
  `FlintChartProps.onError` doc in `flint-chart@1.1.0`.
- Minor, not blocking: the outcomes where nothing is drawn (a refused chart; a cancelled or
  failed call) appear elsewhere on the page but not in this section's list. "the server ran
  without a validator" is not linked to `agents.md#checking-charts-with-flint`.

---

## Other findings (source vs docs)

- **Source bug, `ts/src/index.ts` line 15:** `export const VERSION = "0.1.0";`, while
  `ts/package.json` is `"version": "0.2.0"`. `typescript.md` > `VERSION` repeats `"0.1.0"` as its
  example. The release steps in the root README say to set `VERSION` when tagging, so this was
  missed for 0.2.0. Bump it together with `package.json` for 0.3.0, and make the doc example
  version-neutral (for example `"0.3.0"`, or "the version in `package.json`").
- **Rule 4 (cross-references):** in `chat-ui.md`, the inline mentions `requestInit`, `loading`,
  `renderError` and `fetch` are not linked to `typescript.md#slayerchart`. `chart_toolset`,
  `url_prefix` and `session_of` are not linked to their autoapi entries.

---

## Revision Recommendations

### FAIL Issues (trigger revision)

None.

### PARTIAL Issues (for project author approval)

| Scenario | Page | Gap | Suggested Fix |
|----------|------|-----|---------------|
| S1 | `docs/changelog.md` (+ missing `CHANGELOG.md`) | The include target doesn't exist, so there are no release notes and no 0.3.0 upgrade note | Add `CHANGELOG.md` with a 0.3.0 npm entry: flint-chart 1.1.0 pinned as a dependency; vega/vega-lite/vega-tooltip no longer peers (remove them); `percentScale: "fraction"` |
| S1 | `docs/chat-ui.md` > intro | Flint not defined; pinned version not stated; peer ranges not next to the install command | In `docs/chat-ui.md`, intro: define and link Flint, say it installs with the package at exactly 1.1.0, and list the optional peers CopilotKit 1.80+ and assistant-ui 0.15 |
| S1 | `docs/typescript.md` > entry table, `checkChart` | "nothing beyond `flint-chart`" is misleading; the example says to install `flint-chart` with no version | In `docs/typescript.md`, entry table and `checkChart`: say the package installs `flint-chart` 1.1.0, and use `npm install flint-chart@1.1.0 vega-embed` (check whether vega-embed's peers also need `vega`/`vega-lite`) |
| S1 | `README.md` (root) | No npm command and no link to the docs | In `README.md`, Installation: add the npm command in its own block and a docs link |
| S5 | `docs/chat-ui.md` > Reach the rows route | Cross-origin CORS steps leave out allowed headers, so the page's own Bearer example fails preflight | In `docs/chat-ui.md`, "Another origin": add allowing added headers such as `Authorization` |
| S5 | `docs/chat-ui.md` > Send credentials or headers | No guidance on a changing token in assistant-ui | In `docs/chat-ui.md`, Send credentials…: note that options are fixed at `defineToolkit`, and show a `fetch` closure that reads the current token |
| S6 | `docs/chat-ui.md` > Change the loading box…; `docs/typescript.md` > `<SLayerChart>` | A custom `loading` is one static node that gets no title or size; not stated, and no recipe | In `docs/chat-ui.md`, Change the loading box…: state the limitation and show restyling `<ChartSkeleton>` in your own tool-call view, or a CSS override |
| (S4/S7) | `docs/typescript.md` > `VERSION`; `ts/src/index.ts` | `VERSION` is `"0.1.0"` but the package is 0.2.0 (source bug) | Bump `VERSION` with `package.json` for 0.3.0 and make the doc example version-neutral |
