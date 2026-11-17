"""Validating charts with Flint itself through the flint-chart-mcp sidecar."""

from __future__ import annotations

import contextlib
import json
import os
import socket
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from s_layer_flint_charts import (
    DEFAULT_SIDECAR_COMMAND,
    FLINT_MCP_VERSION,
    FlintSidecar,
    SidecarError,
    ValidationReport,
    report_from_result,
    report_from_text,
)
from tests.test_flint_inputs import INPUTS_FILE

if TYPE_CHECKING:
    from collections.abc import Iterator

SIDECAR = Path(__file__).parent.parent / "ts" / "node_modules" / ".bin" / "flint-chart-mcp"
SIDECAR_ARGS = DEFAULT_SIDECAR_COMMAND[DEFAULT_SIDECAR_COMMAND.index("--transport") :]


def test_the_default_command_runs_the_pinned_release_without_file_access() -> None:
    assert f"flint-chart-mcp@{FLINT_MCP_VERSION}" in DEFAULT_SIDECAR_COMMAND
    assert "--disable-file-reference" in DEFAULT_SIDECAR_COMMAND


def test_a_clean_report() -> None:
    report = report_from_result({"valid": True, "warnings": [], "errors": []})
    assert report == ValidationReport()
    assert report.valid


def test_errors_and_warnings_keep_their_messages() -> None:
    report = report_from_result(
        {
            "valid": False,
            "errors": [{"code": "assembly_failed", "message": "no rows"}],
            "warnings": [{"code": "label-overlap", "message": "labels overlap"}, "bare"],
        }
    )
    assert report.errors == ("no rows",)
    assert report.warnings == ("labels overlap", "bare")


def test_an_implicit_aggregate_warning_stops_the_chart() -> None:
    report = report_from_result(
        {
            "valid": True,
            "errors": [],
            "warnings": [{"code": "implicit-aggregate", "message": "rows share a cell"}],
        }
    )
    assert not report.valid
    assert report.errors == ("rows share a cell",)


def test_invalid_without_errors_still_stops_the_chart() -> None:
    assert report_from_result({"valid": False}).errors == ("Flint cannot draw this chart",)


# Text reports as flint-chart-mcp 1.1's validate_chart writes them for the Vega-Lite backend.
CLEAN = "Nothing to fix: call show with this spec."
TO_FIX = "Nothing is on screen: fix what this report lists, then call show with the whole spec."
NOTED = "Noted (the card draws with these; change nothing now unless the user asks):"
MERGED = (
    "Up to 2 rows share one month × region cell; orders is aggregated with sum "
    '(6 cells from 12 rows). Set "aggregate" on color to choose another operation.'
)


def test_a_clean_text_report() -> None:
    report = report_from_text(CLEAN)
    assert report == ValidationReport()


def test_text_report_errors_and_warnings() -> None:
    text = "\n".join(
        [
            TO_FIX,
            "Fix before it draws:",
            "- ✗ encoding x names a field the data does not have: mnth",
            "Noted (the card draws with these):",
            "- labels overlap",
        ]
    )
    report = report_from_text(text)
    assert report == ValidationReport(
        errors=("encoding x names a field the data does not have: mnth",),
        warnings=("labels overlap",),
    )


def test_a_text_report_of_merged_rows_stops_the_chart() -> None:
    report = report_from_text("\n".join([CLEAN, NOTED, f"- {MERGED}", "- labels overlap"]))
    assert report is not None
    assert not report.valid
    assert report.errors == (MERGED,)
    assert report.warnings == ("labels overlap",)


def test_a_text_report_to_fix_without_findings_still_stops_the_chart() -> None:
    report = report_from_text(TO_FIX)
    assert report is not None
    assert report.errors == ("Flint cannot draw this chart",)


@pytest.mark.parametrize("text", ["", "the chart is fine", '{"valid": true}'])
def test_text_that_is_no_report(text: str) -> None:
    assert report_from_text(text) is None


@pytest.mark.anyio
async def test_a_sidecar_must_be_started() -> None:
    with pytest.raises(SidecarError, match="not started"):
        await FlintSidecar().validate({})


def sidecar_available() -> bool:
    if SIDECAR.exists():
        return True
    if os.environ.get("FLINT_SIDECAR_REQUIRED"):
        pytest.fail(f"{SIDECAR} is missing; run `pnpm install` in ts/")
    return False


@pytest.mark.anyio
async def test_flint_checks_the_charts_the_server_builds() -> None:
    if not sidecar_available():
        pytest.skip("flint-chart-mcp is not installed; run `pnpm install` in ts/")
    cases: dict[str, Any] = json.loads(INPUTS_FILE.read_text())
    async with FlintSidecar((str(SIDECAR), *SIDECAR_ARGS)) as sidecar:
        for name, case in cases.items():
            report = await sidecar.validate(case["input"])
            assert report.valid == (not case["problems"]), (name, report)
            if case["problems"]:
                # Refused because Flint merges rows, not for some other reason.
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
        assert report.errors != ("Flint cannot draw this chart",), report
        with pytest.raises(SidecarError, match="validate_chart failed"):
            await sidecar.validate({"data": {"values": []}})


@pytest.fixture
def http_sidecar() -> Iterator[str]:
    if not sidecar_available():
        pytest.skip("flint-chart-mcp is not installed; run `pnpm install` in ts/")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    args = [arg for arg in SIDECAR_ARGS if arg != "stdio"]
    args[args.index("--transport") + 1 : args.index("--transport") + 1] = ["http"]
    process = subprocess.Popen(
        [str(SIDECAR), *args, "--host", "127.0.0.1", "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 15
        while True:
            with contextlib.suppress(OSError), socket.create_connection(("127.0.0.1", port), 0.2):
                break
            if time.monotonic() > deadline or process.poll() is not None:
                pytest.fail("the flint-chart-mcp http server did not start")
            time.sleep(0.1)
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        process.terminate()
        process.wait(5)


@pytest.mark.anyio
async def test_a_sidecar_over_http(http_sidecar: str) -> None:
    cases: dict[str, Any] = json.loads(INPUTS_FILE.read_text())
    async with FlintSidecar(url=http_sidecar) as sidecar:
        report = await sidecar.validate(cases["orders_heatmap"]["input"])
    assert report.valid


class BrokenSession:
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        raise TimeoutError("timed out")


@pytest.mark.anyio
async def test_a_transport_failure_is_a_sidecar_error() -> None:
    sidecar = FlintSidecar()
    setattr(sidecar, "_session", BrokenSession())  # noqa: B010 - stands in for a dead connection
    with pytest.raises(SidecarError, match="timed out") as raised:
        await sidecar.validate({})
    assert isinstance(raised.value.__cause__, TimeoutError)
