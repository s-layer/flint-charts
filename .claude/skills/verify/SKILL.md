---
name: verify
description: Prove a change to s-layer-flint-charts (Python and TypeScript) works end to end. Use before saying a change is done, before committing, and before opening or updating a pull request.
---

# Verify a change

Run from the repository root:

```bash
uv sync --locked --dev --all-extras
pnpm --dir ts install --frozen-lockfile
prek run --all-files
uv run pytest > /tmp/py.log 2>&1; echo "pytest rc=$?"
cd ts && pnpm lint && pnpm typecheck && pnpm test && pnpm build && pnpm test:browser
```

It passes when every command exits 0. `pnpm test:browser` needs Chromium (`pnpm exec
playwright install chromium`). A Python-only change still needs the TypeScript steps
when it touches the shared inputs.

Take each command's exit status from the command itself. In a pipeline `$?` is the last
command's status, so `cmd | tail` hides a failure. Redirect long output to a file, then
read the file.

## What this covers

- the Python mapping, guard and `show_chart` tool, including the sidecar that runs Flint's
  own validator
- the TypeScript package's lint, types, unit tests and real browser rendering

## What it does not cover

- the TypeScript chart against the real Python rows server: the E2E serves rows from a
  mocked route, and the shared golden file covers most of that gap

## When it fails

- Read the first failure and fix its cause. Do not rerun hoping for a green, and do not
  skip, loosen or delete the failing test to get one.
- If the failure is real but outside the change, say so in the PR and in your report
  rather than working around it.
