"""
Validate assembled charts with Flint itself, through a small Node sidecar.

Flint is a JavaScript library, so the server keeps one Node process running
``flint_validate.mjs``, which calls flint-chart's own ``validateChart`` for the Vega-Lite
backend, and talks to it in JSON lines over stdin and stdout. Needs Node, not any Python extra.
"""

from __future__ import annotations

import asyncio
import contextlib
import itertools
import json
import os
import signal
from pathlib import Path
from typing import TYPE_CHECKING, Self, cast

import orjson

from s_layer_flint_charts._charts import ValidationReport
from s_layer_flint_charts._mapping import FLINT_VERSION

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from types import TracebackType

__all__ = [
    "DEFAULT_SIDECAR_COMMAND",
    "VALIDATOR_SCRIPT",
    "FlintSidecar",
    "SidecarError",
    "report_from_result",
]

VALIDATOR_SCRIPT = Path(__file__).parent / "node" / "flint_validate.mjs"
"""The Node script the sidecar runs. Its last argument is the flint-chart version it insists on."""

DEFAULT_SIDECAR_COMMAND: tuple[str, ...] = (
    "npx",
    "--yes",
    "-p",
    f"flint-chart@{FLINT_VERSION}",
    "node",
    str(VALIDATOR_SCRIPT),
    FLINT_VERSION,
)
"""Runs the validator under ``npx`` with the flint-chart release the mapping is pinned to."""

_ERROR_WARNINGS = frozenset({"implicit-aggregate"})
"""Warnings that stop a chart: Flint merging rows means the grain guard missed a case."""

_LINE_LIMIT = 16 * 1024 * 1024
"""The longest line read from the sidecar: a report is small, but its messages are unbounded."""


class SidecarError(RuntimeError):
    """The sidecar could not start or be reached, or answered with something other than a report."""


def report_from_result(payload: Mapping[str, object]) -> ValidationReport:
    """
    Turn flint-chart's ``ValidateResult`` into a :class:`ValidationReport`.

    ``errors`` become errors. ``warnings`` (which repeat the error-severity entries) become
    warnings, except that an ``implicit-aggregate`` warning counts as an error, since a chart
    whose rows Flint would merge draws a different number than the result holds.
    """
    errors = [_message(entry) for entry in _entries(payload.get("errors"))]
    warnings: list[str] = []
    for entry in _entries(payload.get("warnings")):
        if entry.get("severity") == "error":
            continue
        (errors if entry.get("code") in _ERROR_WARNINGS else warnings).append(_message(entry))
    if not errors and payload.get("valid") is False:
        errors.append("Flint cannot draw this chart")
    return ValidationReport(errors=tuple(errors), warnings=tuple(warnings))


def _entries(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [
        cast("dict[str, object]", entry) if isinstance(entry, dict) else {"message": str(entry)}
        for entry in cast("list[object]", value)
    ]


def _message(entry: Mapping[str, object]) -> str:
    message = entry.get("message")
    return message if isinstance(message, str) else str(dict(entry))


class FlintSidecar:
    """
    A Node process running Flint's ``validateChart``, the ``validator`` of :func:`show_chart`.

    Start one per process and share it: it is an async context manager that spawns the sidecar
    on entry and stops it on exit. Checks are sent one at a time.

    Example:
        .. code-block:: python

            async with FlintSidecar() as sidecar:
                receipt = await show_chart(session, ..., validator=sidecar)

    Args:
        command: The command that starts the sidecar. By default ``npx`` installs the
            flint-chart release the mapping is pinned to and runs :data:`VALIDATOR_SCRIPT` with
            it. To use a flint-chart you install yourself, run ``node`` on the script with
            ``FLINT_CHART_DIR`` set to the package's directory.
        timeout: Seconds to wait for one validation.
        start_timeout: Seconds to wait for the sidecar to start, which includes ``npx``
            downloading flint-chart the first time.
    """

    def __init__(
        self,
        command: Sequence[str] = DEFAULT_SIDECAR_COMMAND,
        *,
        timeout: float = 10.0,
        start_timeout: float = 120.0,
    ) -> None:
        self._command = tuple(command)
        self._timeout = timeout
        self._start_timeout = start_timeout
        self._process: asyncio.subprocess.Process | None = None
        self._lock = asyncio.Lock()
        self._ids = itertools.count(1)
        self.version: str | None = None
        """The flint-chart version the running sidecar loaded."""

    async def __aenter__(self) -> Self:
        try:
            process = await asyncio.create_subprocess_exec(
                *self._command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                limit=_LINE_LIMIT,
                # Its own process group, so stopping it also stops node under npx.
                start_new_session=os.name == "posix",
            )
        except OSError as error:
            raise SidecarError(f"the Flint sidecar could not start: {error}") from error
        self._process = process
        try:
            hello = await self._read(self._start_timeout, "start")
            if "fatal" in hello:
                raise SidecarError(f"the Flint sidecar could not start: {hello['fatal']}")
            if hello.get("ready") is not True:
                raise SidecarError(f"the Flint sidecar started with something else: {hello}")
        except BaseException:
            await self._stop()
            raise
        version = hello.get("version")
        self.version = version if isinstance(version, str) else None
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self._stop()

    async def validate(self, flint_input: Mapping[str, object]) -> ValidationReport:
        """
        Ask Flint whether it can draw ``flint_input``, as the Vega-Lite backend would.

        Raises:
            SidecarError: The sidecar is not started, did not answer in time or at all (one
                that has timed out or exited is stopped and stays gone), or did not answer
                with a report.
        """
        async with self._lock:
            process = self._process
            if process is None or process.stdin is None:
                raise SidecarError(
                    "the Flint sidecar is not started; use `async with FlintSidecar()`"
                )
            request_id = next(self._ids)
            try:
                # orjson, as for the rows the browser fetches: dates as ISO 8601, NaN as null.
                line = orjson.dumps({"id": request_id, "input": flint_input})
            except TypeError as error:  # a value JSON has no form for
                raise SidecarError(f"the chart input is not JSON: {error}") from error
            try:
                process.stdin.write(line + b"\n")
                await process.stdin.drain()
                answer = await self._answer(request_id)
            except SidecarError:
                await self._stop()
                raise
            except OSError as error:  # the pipe closed under us
                await self._stop()
                raise SidecarError(f"the Flint sidecar did not answer: {error}") from error
        if "error" in answer:
            raise SidecarError(f"validateChart failed: {answer['error']}")
        result = answer.get("result")
        if not isinstance(result, dict) or "valid" not in result:
            raise SidecarError(f"the Flint sidecar answered without a report: {answer}")
        return report_from_result(cast("dict[str, object]", result))

    async def _answer(self, request_id: int) -> dict[str, object]:
        """
        Read the answer to ``request_id``, past the late answers of cancelled requests.

        A request cancelled while Flint worked on it still gets its answer, which then waits on
        stdout ahead of the next request's; its id is lower, so it is skipped.
        """
        while True:
            answer = await self._read(self._timeout, "answer")
            answer_id = answer.get("id")
            if answer_id == request_id:
                return answer
            if not isinstance(answer_id, int) or answer_id > request_id:
                raise SidecarError(f"the Flint sidecar answered another request: {answer}")

    async def _read(self, timeout: float, what: str) -> dict[str, object]:
        process = self._process
        assert process is not None and process.stdout is not None
        try:
            raw = await asyncio.wait_for(process.stdout.readline(), timeout)
        except TimeoutError as error:
            raise SidecarError(
                f"the Flint sidecar did not {what} within {timeout:g}s: timed out"
            ) from error
        except ValueError as error:  # a line past _LINE_LIMIT
            raise SidecarError(f"the Flint sidecar sent an overlong line: {error}") from error
        if not raw:
            code = await process.wait()
            raise SidecarError(f"the Flint sidecar exited (status {code})")
        try:
            message: object = json.loads(raw)
        except ValueError as error:
            raise SidecarError(
                f"the Flint sidecar sent something other than JSON: {raw[:200]!r}"
            ) from error
        if not isinstance(message, dict):
            raise SidecarError(
                f"the Flint sidecar sent something other than an object: {message!r}"
            )
        return cast("dict[str, object]", message)

    async def _stop(self) -> None:
        process, self._process = self._process, None
        if process is None:
            return
        if process.stdin is not None:
            process.stdin.close()
        try:
            await asyncio.wait_for(process.wait(), 5)
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGKILL)
                else:  # pragma: no cover - Windows
                    process.kill()
            await process.wait()
