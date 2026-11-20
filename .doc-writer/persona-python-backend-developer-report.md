# Persona Report

**Generated:** 2026-11-20
**Audience:** Python backend developer (advanced)
**Scenarios tested:** 6 (one per persona user_task, plus an upgrade-from-0.2.0 scenario)
**Results:** 0 PASS, 5 PARTIAL, 1 FAIL

## Summary

The new-install path for 0.3.0 reads well and is accurate. Each factual claim in
`agents.md`, `mapping.md` and `grain.md` that I checked against `src/s_layer_flint_charts/`
holds: the JSON-lines Node sidecar, the `npx` default, `FLINT_CHART_DIR`, the version check,
`implicit-aggregate` treated as an error, `percentScale: "fraction"`, the `description=`
fallback to the docstring, and the store limits. The gaps are in what the pages leave out.
Nothing tells a 0.2.0 user that `[validate]`, `FlintSidecar(url=)` and flint-chart-mcp are
gone, or what replaces them (FAIL). The pages also skip how the sidecar lives and fails, that
the default query path needs an async semolina engine, and that stacked charts need declared
additivity in the `s_layer` block.

Two navigation notes apply to every scenario:

- `README.md` (also the PyPI page) has no link to the docs site, and `pyproject.toml` has no
  `[project.urls]`.
- Inline code across `agents.md`, `grain.md` and `mapping.md` (`chart_toolset`, `ChartStore`,
  `FlintSidecar`, `check_grain`, `map_field` and others) is not linked to the API reference
  (Rule 4). The page-level reference exists, but reaching it means going through the sidebar.

---

## Scenario S1: Give a Pydantic AI agent query and chart tools

**Verdict:** PARTIAL

### Navigation Path

1. Started at: `docs/index.rst`
   - Found: install command, a mapping quick start, and a link to `agents` ("to give an agent
     query and chart tools").
   - Followed: `agents`
2. Navigated to: `docs/agents.md` > "The toolset"
   - Found: the extras (`[pydantic-ai,server]`), a complete `chart_toolset` example with
     `ChartStore`, `session_id` and `validator=sidecar`, the query-spec keys, the summary
     contents, the `show_chart` receipt shape, and how the tool description is chosen.
   - Friction: "the model's `description=`" uses "model" for the semolina class on a page where
     "the model" otherwise means the LLM. There is no example of where `description=` goes
     (`class Sales(SemanticView, view="sales", description="...")`), no link to semolina's docs,
     and no mention that semolina >= 0.10.0 is required.
   - Friction: the page never says how the query tools run. Neither `fetch=` nor the
     async-engine requirement appears.
3. Navigated to: API Reference > `s_layer_flint_charts.pydantic_ai.chart_toolset`
   - Found: "fetch: Runs a query. By default each query runs on its view's async engine."
     That answers the question, but only for a reader who opens the reference.

### Source check

- `pydantic_ai._query_tool`: `(view._description or "").strip() or (view.__doc__ or "").strip()`.
  The page describes this correctly.
- `_query._fetch_async` calls `query.aexecute()`. In semolina, that looks up the async registry
  (`register_async_engine`), which is separate from the sync one. A user who registered only a
  sync engine fails on the first query tool call, and `agents.md` never warns them.
- `pyproject.toml` requires `semolina>=0.10.0`, and no page says so.

### Gap Analysis

**Where:** `docs/agents.md` > "The toolset"
**What:** Three things are missing: (1) the default fetch needs an async semolina engine
registered, and `fetch=` is how to supply your own; (2) an example of `description=` on a
`SemanticView`, worded so "model" isn't ambiguous; (3) the semolina >= 0.10.0 requirement.
**Impact:** A user with only a sync engine gets an error on the first tool call and has to
find `fetch` in the API reference. A user can't tell where to put `description=`.
**Suggested Fix:** In `docs/agents.md`, section "The toolset": after the example, add "The
query tools run on each view's async engine (`semolina.register_async_engine`); pass `fetch=`
to run them another way." Change "the model's `description=`" to "the view class's
`description=` (`class Sales(SemanticView, view="sales", description=...)`, which semolina
codegen writes from the view's COMMENT; needs semolina 0.10.0 or later)". Link `chart_toolset`
and `ChartStore` to their reference entries.

---

## Scenario S2: Mount the rows route and tie it to conversations

**Verdict:** PARTIAL

### Navigation Path

1. Started at: `docs/index.rst` > followed `agents`
2. Navigated to: `docs/agents.md` > "The rows route"
   - Found: a Starlette `Mount("/flint", routes=chart_routes(store, session_of))` example, the
     404 cases, compression, and the `url_prefix=` rule. "Limits" covers TTL and the session
     and chart caps, and notes that a route hit doesn't count as a use.
   - Friction: the page never says that `session_of(request)` must return the same id that
     `session_id(ctx)` gave the agent run. I found that rule only in `docs/chat-ui.md` ("it
     must name the same conversation the agent run used as its `session_id`"), a frontend page
     a backend developer would not open.
   - Friction: the example reads `request.session` without saying it needs Starlette's
     `SessionMiddleware`. Without it, `request.session` raises. Nothing shows how to set the
     conversation cookie when a chat starts.
   - Friction: no FastAPI form is shown (`app.mount("/flint", Starlette(routes=...))`), and
     nothing says `url_prefix` must include any outer mount path or `root_path`.
3. Followed: "See also" > `chat-ui.md` > "Reach the rows route" for the same-origin and CORS
   guidance, which is useful and correct.

### Source check

- `server.chart_routes`: `session_of` may be sync or async. The route returns 404 when it gives
  `None`, an unknown id, or a session without that chart. It uses `store.get()`, which does not
  refresh the TTL. The docs are correct on all of this.
- `_store.ChartStore` defaults are ttl=3600, max_sessions=1000, max_results=20 and
  max_charts=50, matching "Limits".

### Gap Analysis

**Where:** `docs/agents.md` > "The rows route"
**What:** The page doesn't state the one invariant that ties the two halves together
(`session_of(request) == session_id(ctx)` for the same conversation), and its example depends
on middleware it doesn't mention.
**Impact:** The most likely integration bug is the first chart showing "This chart's data has
expired", and the backend page gives no way to diagnose it.
**Suggested Fix:** In `docs/agents.md`, section "The rows route": add "`session_of` must
return the same id your `session_id` function gave the agent run for that conversation, or the
route answers 404." Note that the example assumes `SessionMiddleware` with a signed cookie.
Add a FastAPI line (`app.mount("/flint", Starlette(routes=chart_routes(store, session_of)))`),
and say that `url_prefix` is the full path from the origin.

---

## Scenario S3: Validate charts with the Flint sidecar

**Verdict:** PARTIAL

### Navigation Path

1. Started at: `docs/index.rst` > followed `agents`
2. Navigated to: `docs/agents.md` > "Checking charts with Flint"
   - Found: a clear explanation. `FlintSidecar` runs a Node script that ships with the package
     and calls Flint's `validateChart` as the Vega-Lite backend would. They talk in JSON lines.
     Errors and `implicit-aggregate` stop a chart, and other warnings go to the model. The
     default is `npx`, which downloads the pinned `flint-chart`. For offline images, the page
     shows `node` with `VALIDATOR_SCRIPT`, `FLINT_VERSION` and `FLINT_CHART_DIR`. It notes the
     version check and the no-validator fallback. This covers the never_assume item well.
   - Friction: "Node must be installed" gives no version. flint-chart 1.1.0 declares
     `"engines": {"node": ">=18"}`.
   - Friction: the self-install path doesn't say which version to install. The page never
     says `FLINT_VERSION` is 1.1.0 and gives no `npm install flint-chart@<FLINT_VERSION>` line.
   - Friction: lifecycle. The toolset example only says `# start it once, with async with,
     when the app starts`. There is no lifespan snippet. A sidecar passed to `chart_toolset`
     but never entered raises on every chart.
   - Friction: failure modes are missing. The page doesn't say what the app sees when the
     sidecar can't start, times out or dies.
3. Navigated to: API Reference > `FlintSidecar`, `FlintSidecar.validate`, `SidecarError`
   - Found: `timeout` (10s) and `start_timeout` (120s). `validate` raises `SidecarError` "not
     started, did not answer in time or at all (one that has timed out or exited is stopped
     and stays gone)".

### Source check

- `_sidecar.FlintSidecar`: on a timeout or exit, `validate()` calls `_stop()` and raises
  `SidecarError`. Every later call raises "the Flint sidecar is not started" until the app
  enters the context manager again.
- `_charts.show_chart` does not catch `SidecarError`, and the `show_chart` tool in
  `pydantic_ai.py` only converts `receipt.ok == False` to `ModelRetry`. A sidecar failure
  therefore propagates out of the tool and fails the agent run; the model never hears about
  it. After one slow validation (over 10s), charting fails for the rest of the process's life.
- `node/flint_validate.mjs` matches the page on the protocol, the `FLINT_CHART_DIR` lookup,
  the version refusal and the Vega-Lite backend.

### Gap Analysis

**Where:** `docs/agents.md` > "Checking charts with Flint"
**What:** Five things are missing: the Node version (18 or later), the pinned flint-chart
version and its install command, a startup and shutdown example, the `timeout=` and
`start_timeout=` options, and what happens on failure (a `SidecarError` ends the agent run,
and a timed-out sidecar stays stopped until restarted).
**Impact:** A production deployment can lose chart validation, and with it every chart, after
one slow call, with no hint in the docs.
**Suggested Fix:** In `docs/agents.md`, section "Checking charts with Flint": state "Node 18 or
later". Give the pinned version (`FLINT_VERSION`, currently 1.1.0) and `npm install
flint-chart@1.1.0` for the self-install case. Add a Starlette lifespan example (`async with
sidecar: yield`). Add a short "When the sidecar fails" paragraph: `SidecarError` is raised
from the tool call and is not sent to the model; after a timeout or exit the sidecar stays
stopped until it is entered again; `timeout=` and `start_timeout=` tune the waits. Link
`FlintSidecar` and `SidecarError` to the reference.

---

## Scenario S4: Understand what the grain guard refuses

**Verdict:** PARTIAL

### Navigation Path

1. Started at: `docs/index.rst`. The index doesn't link `grain`; I found it in the sidebar
   ("Rows and the grain guard"). `agents.md` > "See also" links it too.
2. Navigated to: `docs/grain.md` > "Checking the grain"
   - Found: a rule table with refused examples and the messages the model sees, the exemptions
     for scatter, distribution and table charts, which chart types stack, the `stackMode:
     "layered"` escape, and stacked-area zero-filling. This page is a good fit for the need.
   - Friction: "A metric whose additivity is unknown is not stacked" reads as though the chart
     is quietly drawn layered. In fact the chart is refused, and the table has no row for it.
   - Friction: nothing tells a toolset user where a metric's additivity comes from, or what to
     add so that "revenue by month stacked by region" is allowed.
3. Navigated to: `docs/mapping.md`, for "additivity"
   - Found: "The block's `aggregation.additivity` wins". This is the only hint, and it sits in
     the Amount/Price context.
4. Navigated to: API Reference > `Metric`
   - Found: "`additivity` is the metric's additivity from its `s_layer` block or its semantic
     definition".

### Source check

- `_grain._stacking_problems`: when additivity is `None`, the chart is refused with "a {chart}
  sums {metric} across {color}, but its additivity is not declared, so its sum may be wrong;
  use a Line Chart or a Grouped Bar Chart, or take color off".
- `_query.result_columns` builds `Metric(additivity=block.additivity)` from the field's
  `semantic_format` only. `SemanticFormat.additivity` is the stated `aggregation.additivity`,
  else the kind's implied one, and only `percentage` and `score` imply anything
  (`non_additive`). So in the toolset, a `currency` or `count` metric, or a metric with no
  block at all, can't be stacked by color unless its block states `aggregation: {additivity:
  additive}`. Nothing is derived from the semantic definition, which contradicts the `Metric`
  docstring for the toolset path.
- The table's other messages match `_grain.py`, with light paraphrase: the real shared-mark
  message adds "(for example months drawn as quarters)". The table omits refusals that
  `show_chart` itself makes (`_charts.assemble_chart` and `show_chart`): an unknown chart
  type, no encodings, and "there is no result …; run the query again" for an expired or
  evicted result.

### Gap Analysis

**Where:** `docs/grain.md` > "Checking the grain" (table and stacking paragraph); API
Reference > `Metric`
**What:** An undeclared-additivity metric is refused, not "not stacked", and the table has no
row for it. The page never says that under `chart_toolset` additivity comes only from the
field's `s_layer` block, so stacking needs `aggregation.additivity` declared. The `Metric`
docstring wrongly implies the semantic definition is used.
**Impact:** The most common stacked chart is refused for most real views, and the developer
can't tell from the docs what to change.
**Suggested Fix:** In `docs/grain.md`, section "Checking the grain": add a table row ("a stacked
bar of a metric whose block declares no additivity" → "its additivity is not declared, so its
sum may be wrong"). Change "is not stacked" to "is refused on a stacking chart". Add: "With
`chart_toolset`, a metric's additivity comes from its `s_layer` block (`aggregation.additivity`;
`percentage` and `score` imply non-additive). Declare `additive` on metrics you want stacked."
Either fix the `Metric` docstring or make the toolset pass the semantic definition's
additivity. Optionally list `show_chart`'s own refusals.

---

## Scenario S5: Map semantic formats to Flint types

**Verdict:** PARTIAL

### Navigation Path

1. Started at: `docs/index.rst` > Quick Start (`map_field` / `semantic_types`) > followed
   `mapping`
2. Navigated to: `docs/mapping.md`
   - Found: a full `value.kind` → Flint type table, rules (query grain wins, timelines not
     cycles, additivity decides Amount or Price, fallback by Arrow type), `value_form`, and a
     clear percentage section. Percentages carry `percentScale: "fraction"` and
     `intrinsicDomain [0, 1]`, and `fit_to_values` widens to `PercentageChange`. The page
     explains why `percentScale` is stated (flint-chart#154). The example is realistic and
     complete. This covers the never_assume item.
   - Friction: the page describes `map_field` but never says that `chart_toolset` applies the
     mapping itself, from each semolina field's `semantic_format=`, or which of `map_field`'s
     inputs the toolset supplies.
   - Friction: "written against flint-chart `FLINT_VERSION`" doesn't give the version.

### Source check

- `_mapping._from_block` matches every row of the table, including the `duration` unit
  spellings, geo levels, temporal grains and the Amount/Price split. The percentage block sets
  `percent_scale="fraction"` and `percent_to_fraction` for 0-100 scale.
  `fit_to_values` → `PercentageChange` with domain `(min(0, low), max(1, high))`, keeping
  `percentScale`. This matches the page and the `fit_to_values` docstring example.
- `_query.result_columns` calls `map_field(block, type, grain=..., label=...)` without
  `aggregation=` or `additivity=`. Through the toolset, then:
  - An unblocked integer count metric falls back to `Number`, not the `Count` the page
    promises.
  - A currency metric whose block states no additivity is always `Amount`, because "pass the
    additivity the semantic definition declares" is not possible.

### Gap Analysis

**Where:** `docs/mapping.md` > rules list ("Additivity decides Amount or Price", "A field
without a block falls back…")
**What:** The page doesn't say how the mapping behaves under `chart_toolset`, which takes the
block from the semolina field's `semantic_format=` and passes neither `aggregation=` nor
`additivity=`. So the "integer `count` metric → `Count`" fallback and the "pass the
additivity" advice don't apply there.
**Impact:** A toolset user predicts `Count` or `Price` and gets `Number` or `Amount`. It's
minor, but it's a factual mismatch with what the toolset emits.
**Suggested Fix:** In `docs/mapping.md`, after the rules list, add: "`chart_toolset` maps each
column for you from the semolina field's `semantic_format=`. It doesn't pass `aggregation=`
or `additivity=`, so give count metrics a `count` block and price metrics `aggregation:
{additivity: non_additive}`." State the pinned version next to `FLINT_VERSION`.

---

## Scenario S6: Upgrade a 0.2.0 backend that used `[validate]` and `FlintSidecar(url=...)`

**Verdict:** FAIL

### Navigation Path

1. Started at: `docs/index.rst`. Nothing about upgrading or what changed in 0.3.0.
2. Navigated to: sidebar "Release notes" (`docs/changelog.md`)
   - Found: an include of `../CHANGELOG.md`. That file isn't in the tree. CI generates it at
     docs and release time with git-cliff (`.cliff.toml`, `docs.yml`), which prints only each
     conventional commit's subject line and skips `docs:` commits. Whatever it shows, it
     can't hold migration steps such as "replace `url=` with …".
3. Navigated to: `docs/agents.md` > install line and "Checking charts with Flint"
   - Found: the current setup only (`[pydantic-ai,server]` extras, a `FlintSidecar()` that
     spawns Node). No mention that `[validate]` was removed, that `url=` is gone, that
     flint-chart-mcp is no longer used, or that the validator can no longer be a separate
     service.
4. Navigated to: API Reference > `FlintSidecar`
   - Found: the signature `(command=DEFAULT_SIDECAR_COMMAND, *, timeout, start_timeout)`.
     There's no `url`, and no deprecation note.
5. Navigated to: `docs/mapping.md`
   - Found: the current `percentScale: "fraction"` behaviour. Nothing says the percent_points
     workaround is gone or that percentage annotations in receipts changed.

### Source check

- `pyproject.toml` `[project.optional-dependencies]` now holds only `server` and `pydantic-ai`.
  `pip install 's-layer-flint-charts[validate]'` only warns about an unknown extra, so the
  user gets no validator dependencies and no signal.
- `_sidecar.FlintSidecar.__init__` has no `url` parameter, so `FlintSidecar(url=...)` raises
  `TypeError`. The class always spawns a local process (`asyncio.create_subprocess_exec`), so
  a deployment that ran flint-chart-mcp as a separate container must now put Node 18+ (and
  either network for `npx` or a preinstalled `flint-chart@1.1.0` plus `FLINT_CHART_DIR`) in
  the Python app's image.
- `semolina>=0.10.0` is a new floor, and a project pinned to semolina 0.9 will fail to
  resolve.
- No `percent_points` symbol remains anywhere in `src/`. Whether it was public API in 0.2.0
  can't be checked from the tree, so the release notes must say.

### Gap Analysis

**Where:** No page exists, and the release notes page depends on an auto-generated
CHANGELOG.md of commit subjects.
**What:** There is no upgrade guidance for 0.2.0 users. Nothing says that `[validate]` is
removed (and pip will not complain), that `FlintSidecar(url=)` is removed with no remote mode,
that flint-chart-mcp is no longer used and Node 18+ must run beside the Python app, that
semolina >= 0.10.0 is required, or that percentages now carry `percentScale: "fraction"` and
the percent_points workaround is gone.
**Impact:** An upgrader can't tell what to change. They find out from a `TypeError` at
startup, or a silently missing extra, and then must redesign their deployment topology with no
guidance.
**Suggested Fix:** Add an "Upgrading from 0.2.0" section, either in `docs/agents.md` or as its
own page linked from the index and the release notes. Cover: drop `[validate]` from installs;
replace `FlintSidecar(url=...)` (and the flint-chart-mcp service) with `FlintSidecar()`, or
`FlintSidecar(("node", str(VALIDATOR_SCRIPT), FLINT_VERSION))` plus `FLINT_CHART_DIR` for
offline images, in the same process environment, with Node 18+; upgrade semolina to 0.10.0+;
expect `percentScale: "fraction"` on percentage columns and remove any percent_points
handling; set `description=` on views (via semolina codegen) to improve tool descriptions.
Because the generated changelog drops `docs:` commits and bodies, keep this text in a
hand-written page rather than relying on the changelog.

---

## Other observations (non-blocking)

- Rule 1: `grain.md` > "Checked against Flint" and `mapping.md`'s last paragraph talk about
  the test suite and CI. This is reassuring but maintainer-facing, and could be reworded as a
  guarantee ("every chart the guard passes is one Flint draws without aggregating").
- `grain.md` says only "size for a pie". The source also treats `theta` as the pie's measure
  channel.
- `agents.md` lists the query summary's fields but omits `description` per column, `view`, and
  the `capped` message.

---

## Revision Recommendations

### FAIL Issues (trigger revision)

| Scenario | Page | Gap | Suggested Fix |
|----------|------|-----|---------------|
| S6 | (no page); `docs/changelog.md` | No upgrade guidance: `[validate]` extra removed (pip only warns), `FlintSidecar(url=)` removed with no remote mode, flint-chart-mcp replaced by a local Node 18+ process, semolina>=0.10.0 required, percentScale/percent_points change. The generated changelog holds only commit subjects and can't carry migration steps. | Add a hand-written "Upgrading from 0.2.0" section or page, linked from the index and the release notes, covering each removal, its replacement, the deployment-topology change and the new semolina floor. |

### PARTIAL Issues (for project author approval)

| Scenario | Page | Gap | Suggested Fix |
|----------|------|-----|---------------|
| S1 | `docs/agents.md` > The toolset | Default fetch needs an async semolina engine; `fetch=` not mentioned; "the model's `description=`" ambiguous, with no example; semolina >= 0.10.0 not stated. | In `docs/agents.md`, section "The toolset": add the async-engine/`fetch=` sentence, a `description=` class-keyword example, and the semolina version. Link symbols to the reference. |
| S2 | `docs/agents.md` > The rows route | The `session_of` == `session_id` invariant only appears in `chat-ui.md`; the example needs `SessionMiddleware`, unstated; no FastAPI form; `url_prefix` must be the full path. | In `docs/agents.md`, section "The rows route": state the invariant, note the middleware, add a FastAPI mount line, and clarify `url_prefix`. |
| S3 | `docs/agents.md` > Checking charts with Flint | No Node version (>=18); no pinned flint-chart version or install command; no lifespan example; `SidecarError` ends the agent run, and a timed-out sidecar stays stopped, both undocumented. | In `docs/agents.md`, section "Checking charts with Flint": add Node 18+, the `FLINT_VERSION` value and npm command, a lifespan snippet, `timeout`/`start_timeout`, and a "When the sidecar fails" paragraph. |
| S4 | `docs/grain.md` > Checking the grain; API ref `Metric` | Undeclared additivity is refused (not "not stacked"), with no table row; under the toolset, additivity comes only from the `s_layer` block, so stacking needs `aggregation.additivity`; the `Metric` docstring claims the semantic definition is used. | In `docs/grain.md`: add the row, fix the wording, and explain where toolset additivity comes from. Fix the `Metric` docstring, or change the code. |
| S5 | `docs/mapping.md` > rules list | The page doesn't say the toolset maps columns from semolina `semantic_format=` without `aggregation=`/`additivity=`, so the Count fallback and the Price-from-definition advice don't apply there; pinned version not stated. | In `docs/mapping.md`, after the rules: add a toolset paragraph and state the `FLINT_VERSION` value. |
| all | `README.md`, `pyproject.toml` | README/PyPI page has no docs link; inline code is not cross-referenced to the API reference (Rule 4). | Add a Documentation link to the README and `[project.urls]`; link the main symbols in `agents.md`, `grain.md` and `mapping.md`. |
