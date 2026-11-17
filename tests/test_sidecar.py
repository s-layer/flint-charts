"""Validating charts with Flint itself through the Node validateChart sidecar."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest

from s_layer_flint_charts import (
    DEFAULT_SIDECAR_COMMAND,
    FLINT_VERSION,
    VALIDATOR_SCRIPT,
    FlintSidecar,
    SidecarError,
    ValidationReport,
    report_from_result,
)
from tests.test_flint_inputs import INPUTS_FILE

FLINT_DIR = Path(__file__).parent.parent / "ts" / "node_modules" / "flint-chart"


def test_the_default_command_runs_the_script_with_the_pinned_release() -> None:
    assert DEFAULT_SIDECAR_COMMAND[:4] == ("npx", "--yes", "-p", f"flint-chart@{FLINT_VERSION}")
    assert DEFAULT_SIDECAR_COMMAND[-3:] == ("node", str(VALIDATOR_SCRIPT), FLINT_VERSION)


def test_the_script_ships_inside_the_package() -> None:
    assert VALIDATOR_SCRIPT.is_file()
    package = sys.modules["s_layer_flint_charts"].__file__
    assert package is not None
    assert VALIDATOR_SCRIPT.parent == Path(package).parent / "node"
    # The manifest FLINT_VERSION is read from sits beside it.
    assert (VALIDATOR_SCRIPT.parent / "package.json").is_file()


def test_a_clean_report() -> None:
    report = report_from_result({"valid": True, "warnings": [], "errors": []})
    assert report == ValidationReport()
    assert report.valid


def test_errors_and_warnings_keep_their_messages() -> None:
    report = report_from_result(
        {
            "valid": False,
            "errors": [{"severity": "error", "code": "assembly_failed", "message": "no rows"}],
            "warnings": [
                {"severity": "error", "code": "assembly_failed", "message": "no rows"},
                {"severity": "warning", "code": "label-overlap", "message": "labels overlap"},
                "bare",
            ],
        }
    )
    # validateChart repeats error-severity entries under warnings; they are reported once.
    assert report.errors == ("no rows",)
    assert report.warnings == ("labels overlap", "bare")


def test_an_implicit_aggregate_warning_stops_the_chart() -> None:
    report = report_from_result(
        {
            "valid": True,
            "errors": [],
            "warnings": [
                {"severity": "warning", "code": "implicit-aggregate", "message": "rows share"}
            ],
        }
    )
    assert not report.valid
    assert report.errors == ("rows share",)


def test_invalid_without_errors_still_stops_the_chart() -> None:
    assert report_from_result({"valid": False}).errors == ("Flint cannot draw this chart",)


@pytest.mark.anyio
async def test_a_sidecar_must_be_started() -> None:
    with pytest.raises(SidecarError, match="not started"):
        await FlintSidecar().validate({})


@pytest.mark.anyio
async def test_a_missing_command_is_a_sidecar_error() -> None:
    with pytest.raises(SidecarError, match="could not start"):
        async with FlintSidecar(("/nonexistent/node-for-flint",)):
            pass


# Fake sidecars: a Python one-liner that speaks (or garbles) the protocol, so these run anywhere.
def fake(script: str) -> tuple[str, ...]:
    return (sys.executable, "-c", script)


HELLO = 'import sys, json; print(json.dumps({"ready": True, "version": "9.9.9"}), flush=True)\n'
ECHO_RESULT = (
    HELLO
    + "for line in sys.stdin:\n"
    + "    r = json.loads(line)\n"
    + "    print(json.dumps({'id': r['id'], 'result': r['input']['result']}), flush=True)\n"
)


@pytest.mark.anyio
async def test_a_result_is_read_as_a_report() -> None:
    result = {
        "valid": True,
        "errors": [],
        "warnings": [{"severity": "warning", "code": "implicit-aggregate", "message": "merged"}],
    }
    async with FlintSidecar(fake(ECHO_RESULT)) as sidecar:
        assert sidecar.version == "9.9.9"
        first = await sidecar.validate({"result": result})
        second = await sidecar.validate({"result": {"valid": True}})
    assert first.errors == ("merged",)
    assert second == ValidationReport()


@pytest.mark.parametrize(
    ("script", "match"),
    [
        ('import json; print(json.dumps({"fatal": "no flint here"}))', "no flint here"),
        ('print("npm notice: hello")', "other than JSON"),
        ('import json; print(json.dumps({"hello": 1}))', "something else"),
        ("import sys; sys.exit(3)", r"exited \(status 3\)"),
    ],
)
@pytest.mark.anyio
async def test_a_sidecar_that_does_not_start_right(script: str, match: str) -> None:
    with pytest.raises(SidecarError, match=match):
        async with FlintSidecar(fake(script)):
            pass


@pytest.mark.parametrize(
    ("answer", "match"),
    [
        ("{'id': r['id'], 'error': 'boom'}", "validateChart failed: boom"),
        ("{'id': r['id'], 'result': {'no': 'report'}}", "without a report"),
        ("{'id': r['id'] + 1, 'result': {'valid': True}}", "another request"),
    ],
)
@pytest.mark.anyio
async def test_answers_that_are_not_a_report(answer: str, match: str) -> None:
    script = (
        HELLO
        + "for line in sys.stdin:\n    r = json.loads(line)\n"
        + f"    print(json.dumps({answer}), flush=True)\n"
    )
    async with FlintSidecar(fake(script)) as sidecar:
        with pytest.raises(SidecarError, match=match):
            await sidecar.validate({})


@pytest.mark.anyio
async def test_a_sidecar_that_hangs_times_out_and_stays_gone() -> None:
    script = HELLO + "import time\nfor line in sys.stdin:\n    time.sleep(30)\n"
    async with FlintSidecar(fake(script), timeout=0.2) as sidecar:
        with pytest.raises(SidecarError, match="timed out"):
            await sidecar.validate({})
        with pytest.raises(SidecarError, match="not started"):
            await sidecar.validate({})


@pytest.mark.anyio
async def test_a_sidecar_that_exits_mid_answer() -> None:
    script = HELLO + "sys.stdin.readline()\nsys.exit(2)\n"
    async with FlintSidecar(fake(script)) as sidecar:
        with pytest.raises(SidecarError, match="exited"):
            await sidecar.validate({})


@pytest.mark.anyio
async def test_an_input_json_cannot_hold_keeps_the_sidecar() -> None:
    async with FlintSidecar(fake(ECHO_RESULT)) as sidecar:
        with pytest.raises(SidecarError, match="not JSON"):
            await sidecar.validate({"value": float("nan")})
        assert await sidecar.validate({"result": {"valid": True}}) == ValidationReport()


# The real script, with the flint-chart pinned in ts/package.json.
def node_sidecar(*args: str) -> tuple[tuple[str, ...], dict[str, str]]:
    node = shutil.which("node")
    if node is None or not FLINT_DIR.exists():
        if os.environ.get("FLINT_SIDECAR_REQUIRED"):
            pytest.fail(f"node or {FLINT_DIR} is missing; run `pnpm install` in ts/")
        pytest.skip("node or flint-chart is not installed; run `pnpm install` in ts/")
    return (node, str(VALIDATOR_SCRIPT), *args), {"FLINT_CHART_DIR": str(FLINT_DIR)}


@pytest.fixture
def flint_env(monkeypatch: pytest.MonkeyPatch) -> tuple[str, ...]:
    command, env = node_sidecar(FLINT_VERSION)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return command


@pytest.mark.anyio
async def test_flint_checks_the_charts_the_server_builds(flint_env: tuple[str, ...]) -> None:
    cases: dict[str, Any] = json.loads(INPUTS_FILE.read_text())
    async with FlintSidecar(flint_env) as sidecar:
        assert sidecar.version == FLINT_VERSION
        for name, case in cases.items():
            report = await sidecar.validate(case["input"])
            assert report.valid == (not case["problems"]), (name, report)
            if case["problems"]:
                # Refused because Flint merges rows, caught by the warning's code.
                assert any("is aggregated with" in error for error in report.errors), report
        broken = cases["orders_heatmap"]["input"]
        missing = {
            **broken,
            "chart_spec": {
                **broken["chart_spec"],
                "encodings": {**broken["chart_spec"]["encodings"], "x": {"field": "nope"}},
            },
        }
        report = await sidecar.validate(missing)
        assert not report.valid
        assert "nope" in " ".join(report.errors), report
        empty = await sidecar.validate({"data": {"values": []}})
        assert not empty.valid
        assert empty.errors != ("Flint cannot draw this chart",), empty


@pytest.mark.anyio
async def test_the_script_refuses_another_flint_version(monkeypatch: pytest.MonkeyPatch) -> None:
    command, env = node_sidecar("0.0.1")
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(SidecarError, match=f"found flint-chart {FLINT_VERSION}.*expected 0.0.1"):
        async with FlintSidecar(command):
            pass


@pytest.mark.anyio
async def test_the_script_says_when_flint_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    command, _ = node_sidecar(FLINT_VERSION)
    monkeypatch.setenv("FLINT_CHART_DIR", str(tmp_path))
    monkeypatch.setenv("PATH", str(Path(command[0]).parent))
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SidecarError, match="flint-chart is not installed"):
        async with FlintSidecar(command):
            pass


@pytest.mark.anyio
async def test_the_script_finds_flint_beside_a_bin_dir_on_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Where `npx -p flint-chart@X` puts it: <cache>/node_modules/flint-chart, with
    # <cache>/node_modules/.bin on PATH.
    command, _ = node_sidecar(FLINT_VERSION)
    node_modules = FLINT_DIR.parent
    monkeypatch.delenv("FLINT_CHART_DIR", raising=False)
    path = os.pathsep.join([str(node_modules / ".bin"), str(Path(command[0]).parent)])
    monkeypatch.setenv("PATH", path)
    monkeypatch.chdir(tmp_path)
    async with FlintSidecar(command) as sidecar:
        assert sidecar.version == FLINT_VERSION
