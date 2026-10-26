# Project Documentation Rules

These rules are specific to this project and extend the universal quality rules
enforced by all doc-writer agents.

## Project Rules

- The repository ships two packages: `s-layer-flint-charts` (Python) and
  `@s-layer/flint-charts` (npm). Say which one a page or example is about, and never
  mix their install commands in one block.
- Every TypeScript example must typecheck against the published entry points
  (`@s-layer/flint-charts`, `/react`, `/copilotkit`, `/assistant-ui`); never import
  from `src/` paths.
- Use "show_chart result" or "receipt" for what the tool answers with, "rows route"
  for `GET {prefix}/charts/{id}/rows`, and "Flint input" for the chart object.
- The reader-facing messages quoted in the docs must match `describeError` exactly.
- The author is "Anentropic". Never write a personal name for the maintainer.
