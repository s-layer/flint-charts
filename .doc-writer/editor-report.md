# Editor Report

**Generated:** 2026-11-20
**Files reviewed:** 7 (docs/agents.md, docs/chat-ui.md, docs/grain.md, docs/mapping.md, docs/typescript.md, README.md, ts/README.md)
**Changes made:** 41
  - BLOCKING: 28 (4 accuracy fixes, 22 cross-reference links added, 2 open items for the Author or maintainer)
  - SUGGESTION: 10
  - NITPICK: 3

## Summary

The pages changed since v0.2.0 describe the 0.3.0 release correctly in substance: no page still
mentions the vega peers, the Vite `chart.js` workaround, `percent_points`, the `validate` extra,
`flint-chart-mcp` or `FlintSidecar(url=)`. The fixes were precision ones (the blank-description
fallback, when the validator script checks the Flint version, `percentScale` missing from the
mapping table) plus API cross-links on the Python pages, which had none. One release blocker
sits outside the docs: `VERSION` in `ts/src/index.ts` is still `"0.1.0"`.

Scope: update mode, the pages and READMEs changed since tag v0.2.0. No page carried
`INTERNAL NOTES FOR EDITOR` comments, so accuracy was checked claim by claim against
`src/s_layer_flint_charts/` and `ts/src/`. `docs/changelog.md` was ignored as instructed.

---

## Outside the docs (not fixed)

### BLOCKING

| Location | Description | Fix |
|---|---|---|
| `ts/src/index.ts` line 15 | `VERSION = "0.1.0"` but `ts/package.json` is now `0.2.0` (commit 4ac4c31 bumped only `package.json`). `ts/test/index.test.ts` asserts `VERSION === pkg.version`, so the TypeScript tests fail, and README.md's release steps say to set both. | Not fixed (source code, outside the editor's remit). Set `VERSION` to `"0.2.0"`. |

---

## docs/agents.md

### BLOCKING

| Section | Description | Fix |
|---|---|---|
| The toolset | Accuracy (#22): the doc gave the docstring fallback only "when it has no `description=`". In `_query_tool`, a blank or whitespace-only `description=` also counts as none. The phrase "the model's `description=`" also read as the LLM on a page where "the model" means the LLM. | Rewritten: the description comes from the view class's `description=`; "A view with no `description=`, or a blank one, falls back to its class docstring." |
| Checking charts with Flint | Accuracy: "The script refuses to start with any other `flint-chart` version" holds only when the expected version is passed as the script's last argument (`flint_validate.mjs` accepts any version without it). | Now says the script checks the `flint-chart` it finds against the version in its last argument and refuses to start on a mismatch. |
| The toolset, Checking charts with Flint | Rule 4: unlinked API symbols. | Linked the first mentions of `chart_toolset`, `ChartStore` and `FlintSidecar` to the autoapi entries (3 links). |

### SUGGESTION

| Section | Description | Fix |
|---|---|---|
| The rows route | Deslop: "rather than" (Claude tell). | "kept per chart, not per result". |

---

## docs/chat-ui.md

### BLOCKING

| Section | Description | Fix |
|---|---|---|
| Intro | Accuracy and persona: the install note said only "Flint brings the chart libraries it draws with". It did not say that the package itself installs Flint (`flint-chart` is a dependency pinned to one exact release), and Rule 5 never_assume covers this. "The package needs React 18 or later" was too broad, since only the React entry points need React (`react` is an optional peer). | Now: the package depends on Flint (`flint-chart`, pinned to one exact release), which brings its chart libraries, Vega-Lite among them; the React entry points need React 18 or later. |
| Reach the rows route | Rule 4. | Linked `chart_toolset` (1 link). |

### SUGGESTION

| Section | Description | Fix |
|---|---|---|
| Intro | Persona never_assume "What Flint is": Flint was never linked on this page. | Linked the first "Flint" to github.com/microsoft/flint-chart. A one-line definition of Flint is still missing; left for the Author (new content). |
| Reach the rows route | "A chart that answers ... usually means" (inanimate agent, "means the" tell). | "If a chart shows ... on its first draw, the request usually did not reach the route ...". |
| What the reader sees ... | Wh-heading. | Renamed "Charts that can't be drawn". No anchors pointed at the old heading. |
| Charts that can't be drawn | "this means the rows changed", "does not carry the conversation the chart belongs to" (tells). | "so either the rows changed ...", "a request without the chart's conversation". |
| Change the loading box | "carry the classes" (tell). | "have the classes". |

---

## docs/grain.md

### BLOCKING

| Section | Description | Fix |
|---|---|---|
| Writing the rows, Checking the grain, Stacked areas with gaps | Rule 4: the page linked no API symbol. | Linked the first mentions of `chart_rows`, `check_grain`, `FieldType`, `map_field`, `ChartRows`, `UnsupportedColumnError`, `DuplicateColumnError`, `capped`, `ChartRows.to_json()`, `ChartRequest`, `Metric`, `GrainCheck`, `GrainCheck.rows` and `GrainCheck.chart_properties` (14 links). |

### SUGGESTION

| Section | Description | Fix |
|---|---|---|
| Writing the rows | "the chart tells Flint so" (inanimate agent). | "its Flint annotation says so". |
| Writing the rows | "rather than" twice (tells). | "makes its column strings, so no value silently changes"; "Filter or aggregate a capped result further instead of charting it." |
| Checked against Flint | Rule 1: the section cites "the test suite" as its evidence. It is pre-existing and was not changed in this release. | Not changed: removing it would drop the assurance it gives. The Author could restate it without naming the tests. |

---

## docs/mapping.md

### BLOCKING

| Section | Description | Fix |
|---|---|---|
| Type table, `percentage` row | Accuracy (#19): the Annotation column left out `percentScale`, which `map_field` now sets on every percentage (and `fit_to_values` keeps). | The row now lists `percentScale` `"fraction"` alongside `intrinsicDomain`. The prose after it also notes that `PercentageChange` keeps the same `percentScale`. |
| flint-chart#154 paragraph | Accuracy: "Without `percentScale`, Flint would guess ... (flint-chart#154, fixed in Flint 1.1.0)" contradicted itself. In 1.1.0 Flint still guesses when `percentScale` is unset (its own type docs say so); the fix was the new annotation. | Now present tense, "which Flint 1.1.0 answered with `percentScale`". |
| Throughout | Rule 4. | Linked `map_field`, `FieldType`, `value_form` and `FLINT_VERSION` (4 links). |

### SUGGESTION

| Section | Description | Fix |
|---|---|---|
| Title | Wh-heading "How fields map to Flint types". | Renamed "Mapping semantic formats to Flint", which matches the See-also link text in agents.md. The sidebar entry changes with it. |
| Rules list, percentage prose | "rather than a time axis", "turns a percentage ... into", "The result has `fallback=True`", "keeps a column formatted" (tells). | Rephrased, with all code spans, numbers and links kept. |
| Last paragraph | Rule 1: "The TypeScript package's tests check every type ..." cites tests. Pre-existing. | Not changed. |

---

## docs/typescript.md

### SUGGESTION

| Section | Description | Fix |
|---|---|---|
| `checkChart` | With `flint-chart` pinned exactly, a reader who installs it to import `flint-chart/vegalite` should match the pinned release, or the app carries two copies. | "install `flint-chart`, at the release this package pins, and `vega-embed`". |

### NITPICK

| Section | Description | Fix |
|---|---|---|
| `VERSION` | The example value was `"0.1.0"` and the package is now 0.2.0. | Changed to `"0.2.0"`. The scanner reports this as a dropped code span; that is intended. |

---

## ts/README.md

### SUGGESTION

| Section | Description | Fix |
|---|---|---|
| Install | "; see [Charts in a chat UI]" hung off the React sentence after the chart.js note it used to serve was removed. The README also did not say the package installs Flint. | "The package installs Flint, which brings the chart libraries it draws with. The React entry points need React 18 or later ([Charts in a chat UI](...) has the setup)." |

### NITPICK

| Section | Description | Fix |
|---|---|---|
| React | The closing link text named the old chat-ui heading. | "for the options and for charts that can't be drawn". |

---

## README.md

No changes. The one changed line (sidecar tests run Flint's `validateChart` from `ts/node_modules`) is accurate: `flint_validate.mjs` looks in `node_modules/.bin` directories on PATH and in `./node_modules`. README type: blur checks skipped.

---

## Diataxis type integrity

- agents.md and chat-ui.md (how-to): no structural blur. Short "because" clauses ("kept per chart, not per result, because ..."; the JSON-lines sentence) stay, since operators need them.
- grain.md and mapping.md (explanation with reference tables): no structural blur.
- typescript.md (reference): clean. The fragments the scanner flags ("Props: ...", "The package version, such as ...") are normal for reference.

## Terminology Changes

No variants found in the scoped pages. `terminology.yaml` gained source terms `FlintSidecar` and `ChartStore`, and project terms "query tool", "value form", "show_chart result" and "rows request", so the scanner protects them.

| Term | Before | After | Authority |
|---|---|---|---|
| (none normalized) | | | |

## Deslop Measurements

| Page | Likeness before | Likeness after | Fixed | Left on purpose |
|---|---|---|---|---|
| docs/agents.md | 0.48 | 0.40 | "rather than" tell | inanimate_agents ("the script refuses", "the tool refuses": standard idiom), dropped_that, pronouns |
| docs/chat-ui.md | 0.52 | 0.32 | wh_headings, model_fingerprint | inanimate_agents ("the browser asks", "the server refused": literal mechanism), sentence_shape, pronouns |
| docs/grain.md | 0.69 | 0.51 | "rather than" x2, "the chart tells" | triads (lists of value forms and chart types are the content), stock_phrases ("another dimension" is a domain term), pronouns |
| docs/mapping.md | 0.91 | 0.61 | wh_headings, sentence_shape | triads (type lists), count_fragments ("Timelines, never cycles." is an inline-header list lead), pronouns |
| docs/typescript.md | 0.43 | 0.42 | - | count_fragments (reference style), pronouns |
| ts/README.md | 0.62 | 0.23 | model_fingerprint | sentence_length, sentence_openers (108-word page; not meaningful) |
| README.md | 0.20 | 0.20 | - | triads, word_length (tagline and package list) |

## Build

`uv run --group docs sphinx-build -q docs /tmp/claude-0/flint-docs-out`: the only output is the expected missing `CHANGELOG.md` include. A `-n` (nitpicky) build reports no unresolved reference from these pages, so all 22 new `{py:...}` links resolve. Its five other warnings are in autoapi output about `_mapping.FieldType` and `_grain.Metric` and existed before this pass.
