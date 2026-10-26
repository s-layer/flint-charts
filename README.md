# s-layer-flint-charts

Semantic-layer-aware Flint charts for agents: types, grain guard and show_chart tool

This repository holds two packages:

- `s-layer-flint-charts` (Python, repository root): maps semantic-layer field metadata to
  [Flint](https://github.com/microsoft/flint-chart) types, guards chart grain and serves the
  `show_chart` tool.
- `@s-layer/flint-charts` (TypeScript, `ts/`): renders those charts in agent chat UIs.

## Installation

```bash
pip install s-layer-flint-charts
```

## Development

### Quality Gates

Before committing, all code must pass:

```bash
prek run --all-files  # Runs typecheck, lint, format, test
```

Or run individually:
```bash
uv run basedpyright  # Type checking (strict mode)
uv run ruff check    # Linting
uv run ruff format --check  # Formatting
uv run pytest        # Tests
```

### Setup

```bash
# Install dependencies, with every extra
uv sync --dev --all-extras

# The sidecar tests run flint-chart-mcp from ts/node_modules
pnpm --dir ts install

# Install git hooks
prek install
```

### TypeScript package

```bash
cd ts
pnpm install
pnpm lint && pnpm typecheck && pnpm test
pnpm test:browser  # Playwright, in Chromium (pnpm exec playwright install chromium first)
```

### Releases

The packages are released apart. Tag `vX.Y.Z` releases the Python package to PyPI; tag
`ts-vX.Y.Z`, after setting that version in `ts/package.json` and `VERSION` in `ts/src/index.ts`,
releases the npm package.

## License

MIT
