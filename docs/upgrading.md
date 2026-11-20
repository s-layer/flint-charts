---
myst:
  html_meta:
    description: What to change when you move s-layer-flint-charts from 0.2.0 to 0.3.0 and @s-layer/flint-charts from 0.1.0 to 0.2.0
---

(upgrading)=

# Upgrading from 0.2.0

`s-layer-flint-charts` 0.3.0 and `@s-layer/flint-charts` 0.2.0 are released together. Both now
pin Flint (`flint-chart`, Microsoft's semantic chart library) to 1.1.0, up from 1.0.1.
This page lists what to change in each package.

## The Python package

### Drop the `validate` extra

0.3.0 has two extras, `server` and `pydantic-ai`. pip only warns about an extra a package doesn't
have, so you get no error if your install command still names `validate`. Take it out:

```bash
pip install 's-layer-flint-charts[pydantic-ai,server]'
```

The `validate` extra installed `mcp`. You can remove `mcp` too if nothing else in your app uses
it.

### Run the sidecar beside your app

{py:class}`FlintSidecar <s_layer_flint_charts.FlintSidecar>` no longer talks to flint-chart-mcp,
and it has no `url=` parameter, so `FlintSidecar(url=...)` raises a `TypeError`. There is no
remote mode any more. Entering the sidecar always starts a local Node process, which runs a
script that ships with the package and calls Flint's own `validateChart`. To move over:

1. Remove the flint-chart-mcp service or container from your deployment.
2. Install Node 18 or later where the Python app runs.
3. Use `FlintSidecar()` with no arguments if the app can reach the npm registry. `npx` downloads
   flint-chart 1.1.0 the first time the sidecar starts.
4. Without network access, install flint-chart at the pinned version, which
   {py:data}`FLINT_VERSION <s_layer_flint_charts.FLINT_VERSION>` holds (`"1.1.0"`), and point
   `FLINT_CHART_DIR` at it:

   ```bash
   npm install flint-chart@1.1.0
   ```

   ```python
   from s_layer_flint_charts import FLINT_VERSION, VALIDATOR_SCRIPT, FlintSidecar

   # with FLINT_CHART_DIR=/app/node_modules/flint-chart in the environment
   sidecar = FlintSidecar(("node", str(VALIDATOR_SCRIPT), FLINT_VERSION))
   ```

   Without `FLINT_CHART_DIR`, the script also finds a flint-chart installed in `node_modules`
   under the working directory. If the flint-chart it finds is another version, the sidecar
   doesn't start.

A custom `command=` written for flint-chart-mcp won't work either: the command now has to run
{py:data}`VALIDATOR_SCRIPT <s_layer_flint_charts.VALIDATOR_SCRIPT>`. `FLINT_MCP_VERSION` is gone;
`FLINT_VERSION` names the release the sidecar uses. The new `start_timeout` option (120 seconds
by default) sets how long the sidecar may take to start, which includes that first `npx`
download. [Checking charts with Flint](agents.md#checking-charts-with-flint) has the full setup.

### Remove `percent_points`

Flint 1.0.1, which 0.2.0 used, guessed from the values if a percentage column held fractions or
percent points. `percent_points` worked around that, and `show_chart` used it to send a column as
points (multiplied by 100) when Flint would have misread its fractions. Flint 1.1.0 reads a
`percentScale` annotation instead, so:

- `percent_points` is no longer exported. Delete any import or call of it.
- Every percentage column now has `percentScale: "fraction"` in its semantic type, and still has
  it after {py:func}`fit_to_values <s_layer_flint_charts.fit_to_values>` makes it a
  `PercentageChange`.
- The rows always hold fractions, on the rows route too. If your own code read a percentage
  column that the server used to send as points, read it as a fraction now.

[Mapping semantic formats to Flint](mapping.md) explains the annotation.

### Expect a failed check as a problem, not an error

In 0.2.0 a check the sidecar could not make (it timed out, or Node exited) raised
{py:class}`SidecarError <s_layer_flint_charts.SidecarError>` out of `show_chart`, which ended
the agent's run, and the sidecar stayed stopped until your app restarted it. In 0.3.0
`show_chart` answers the model with the problem ("Flint could not check this chart (...)") and
keeps no chart, and the next check starts the sidecar again. If you caught `SidecarError` around
an agent run to recover, you can drop that. A validator of your own signals the same thing by
raising {py:class}`ValidatorError <s_layer_flint_charts.ValidatorError>`, which `SidecarError`
now subclasses.

### Upgrade semolina to 0.10.0

0.3.0 needs `semolina>=0.10.0`; 0.2.0 accepted 0.9.1. A project pinned below 0.10.0 won't
resolve until you raise the pin.

### Check your query tool descriptions

Each query tool now describes its view with the view class's `description=`, and falls back to
the class docstring when `description=` is missing or blank. 0.2.0 used only the docstring.
semolina codegen writes `description=` from the warehouse's view comment, so a regenerated
view may give the model a different description than before:

```python
from semolina import Metric, SemanticView


class Sales(
    SemanticView,
    view="analytics.sales",
    description="Booked orders and revenue, by region and order date",
):
    revenue = Metric[float](label="Revenue")
```

## The npm package

`@s-layer/flint-charts` goes from 0.1.0 to 0.2.0.

### Remove the vega peers

0.2.0 pins `flint-chart` to 1.1.0, where 0.1.0 accepted `~1.0.1`, and npm installs it for you.
Flint 1.1.0 brings the chart libraries it draws with, so `vega`, `vega-lite` and `vega-tooltip`
are no longer peers of this package. Remove them from your
`package.json` unless you import them yourself:

```bash
npm uninstall vega vega-lite vega-tooltip
```

If you list `flint-chart` yourself, pin it to `1.1.0` or drop it. Another version installs a
second copy of Flint beside the one this package uses.

The remaining peers are optional and unchanged: `react` 18 or later, `@copilotkit/react-core`
^1.80.0 and `@assistant-ui/react` ^0.15.0.

### Drop the chart.js external

The 0.1.0 setup had you mark `chart.js` as external in a Vite 8 production build. Flint 1.1.0
installs Chart.js, so the build works without it. Remove `external: ["chart.js"]` from
`vite.config.ts`.

### Percentages arrive as fractions

The rows route now always sends a percentage as a fraction, and Flint formats it from
`percentScale`. `<SLayerChart>` and the adapters need no change. If your own components read
percentage values from the rows, expect fractions.

## See also

- [Release notes](changelog.md)
- [Charts in an agent](agents.md)
- [Charts in a chat UI](chat-ui.md)
- [Mapping semantic formats to Flint](mapping.md)
