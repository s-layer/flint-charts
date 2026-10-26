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
