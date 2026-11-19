---
name: verify
description: Prove a change to s-layer-flint-charts (Python and TypeScript) works end to end. Use before saying a change is done, before committing, and before opening or updating a pull request.
---

# Verify a change

Run from the repository root:

```bash
export CI=true  # CI's skip gate: a skipped test fails the run
uv sync --locked --dev --all-extras
pnpm --dir ts install --frozen-lockfile
uv tool install prek  # once; skip if prek is already on PATH
prek run --all-files
FLINT_SIDECAR_REQUIRED=1 uv run pytest > /tmp/py.log 2>&1; echo "pytest rc=$?"
(cd ts && pnpm lint && pnpm typecheck && pnpm test && pnpm build && pnpm test:browser)
```

It passes when every command exits 0 and every printed `rc=` is 0. `pnpm test:browser`
needs Chromium (`pnpm exec playwright install chromium`). `FLINT_SIDECAR_REQUIRED=1`
makes the sidecar tests fail rather than skip when node or `ts/node_modules` is missing,
as in CI. A Python-only change still needs the TypeScript steps when it touches the
shared inputs.

`CI=true` turns on `tests/ci_skips.py`, which fails the run on any skip not allowed
there, as CI does. Without it a skipped test only shows in the summary, and a run that
skipped what you changed is not a pass.

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
- Python versions other than the one you ran: CI runs a version matrix

## When it fails

- Read the first failure and fix its cause. Do not rerun hoping for a green, and do not
  skip, loosen or delete the failing test to get one.
- If the failure is real but outside the change, say so in the PR and in your report
  rather than working around it.
