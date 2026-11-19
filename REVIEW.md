# Review rules

What a reviewer (the review bot or a person) should look for in a pull request here.
AGENTS.md and CLAUDE.md say how to work in this repository; this file says what to check
in a diff.

## Severity

Tag every finding with one of these:

- **Important**: blocks the merge. A wrong result, a crash, a security problem, a test
  that would pass on broken code, or a break of one of the checks below.
- **Nit**: worth fixing but does not block. Naming, clarity, a small missing test, docs.
- **Pre-existing**: a problem the diff did not cause but sits next to it. Label it so it
  is not mistaken for a regression. It does not block this PR.

Lead with the Important findings. If there are none, say so in one line.

## What to look for

- The grain guard: a chart that would merge rows at the wrong grain is refused, not drawn.
- The Python and TypeScript packages agree: they share `ts/test/flint-inputs.json`, and a
  Python test fails when it is stale.
- The TypeScript package renders in a browser: Playwright draws every guarded case and
  counts marks.

## Diff-triggered checks

Apply a check only when its trigger matches the diff. Each one comes from a miss that
already happened, named under "Source".

- **When the diff touches AGENTS.md, CLAUDE.md, REVIEW.md or anything under `.claude/`**
  Check: Important: list every rule the change adds, loosens or removes, and review the
  rest of the diff against the base branch's copy of these files, not the PR's.
  Source: the review bot reads these files from the PR's own checkout (checked
  2026-11-19), so a PR can rewrite the rules it is reviewed against.
- **When the diff changes the field mapping, the guard or the chart inputs**
  Check: `ts/test/flint-inputs.json` is regenerated (`uv run python -m
  tests.test_flint_inputs`) and both packages' tests pass against it.
  Source: the cross-language golden file is the only check that the two packages agree.
- **When the diff changes the sidecar or its dependencies**
  Check: `pnpm --dir ts install --frozen-lockfile` still works, since the sidecar tests
  need `ts/node_modules`.
  Source: a broken pnpm install would turn 5 sidecar tests into skips (now CI failures).
- **When the diff fixes a bug**
  Check: a test that reproduces the bug and fails without the fix (pytest for Python,
  Vitest or Playwright for TypeScript). When one fix has several cases, each case needs
  its own observed failure, not just the run.
  Source: the failing-test-first rule in CLAUDE.md / AGENTS.md.
- **When the diff adds or changes a test**
  Check: the assertions would fail if the behaviour were wrong. Flag `len(x) > 0`, a
  substring check standing in for a result, `pytest.raises(Exception)` where a specific
  error type exists, fixtures where different answers produce the same number, and checks
  on a field the fixture or generator never varies.
  Source: the 2026-11 test review, which found each of these in s-layer repos
  (`pytest.raises(Exception)` in arrowmodel, a one-row fixture in dbt-s-layer where
  revenue, paid revenue and average order value were all 10).
- **When the diff adds `pytest.skip`, `skipif`, `importorskip` or an `xfail`**
  Check: under CI a skip fails the run unless its reason is allowed in `tests/ci_skips.py`
  with why. A new skip needs CI to install what it needs, a `-m` deselect in the job that
  cannot run it, or an allowlist entry with a reason. A non-strict xfail is Important.
  Source: the 2026-11 test review: 31 dbt-open-sl tests and 8 dbt-s-layer engine tests
  skipped in every CI run while CI stayed green.
- **When the diff deletes, skips or loosens a test, or narrows what a generator produces**
  Check: Important unless the PR says why. A refactor carries its tests with it.
  Source: the coverage-forward refactoring rule (duckdb-semantic-views CLAUDE.md), which
  applies to every s-layer repo.
- **When the diff adds a retry, a rerun, a longer timeout or a sleep to get a test
  passing**
  Check: Important. A flaky test is fixed, or deleted with the reason written down. It is
  never rerun into green.
  Source: standing project rule since 2026-10-19 (never re-run CI for a lucky green).
- **When the diff changes a `uses:` line under `.github/workflows/`**
  Check: refs are tags, not branches or SHAs.
  Source: the GitHub Actions lockfile section in CLAUDE.md / AGENTS.md; a branch ref broke
  every job's setup when the branch was force-pushed.
