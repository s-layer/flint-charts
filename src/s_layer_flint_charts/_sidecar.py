"""
Validate assembled charts with Flint itself, through the ``flint-chart-mcp`` sidecar.

Flint is a JavaScript library, so the server asks a long-running ``flint-chart-mcp`` process
over MCP (stdio or HTTP) instead of reimplementing its checks. Needs the ``validate`` extra.
"""

from __future__ import annotations

import contextlib
import json
from typing import TYPE_CHECKING, Self, cast

from s_layer_flint_charts._charts import ValidationReport

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from types import TracebackType

    from mcp import ClientSession

__all__ = [
    "DEFAULT_SIDECAR_COMMAND",
    "FLINT_MCP_VERSION",
    "FlintSidecar",
    "SidecarError",
    "report_from_result",
]

FLINT_MCP_VERSION = "1.0.1"
"""The flint-chart-mcp release the sidecar client was written and checked against."""

DEFAULT_SIDECAR_COMMAND: tuple[str, ...] = (
    "npx",
    "--yes",
    f"flint-chart-mcp@{FLINT_MCP_VERSION}",
    "--transport",
    "stdio",
    "--backends",
    "vegalite",
    "--disable-file-reference",
)
"""Runs the pinned ``flint-chart-mcp`` on stdio, with local file references off."""

_ERROR_WARNINGS = frozenset({"implicit-aggregate"})
"""Warnings that stop a chart: Flint merging rows means the grain guard missed a case."""


class SidecarError(RuntimeError):
    """The sidecar could not be reached, or answered with something other than a report."""


def report_from_result(payload: Mapping[str, object]) -> ValidationReport:
    """
    Turn ``validate_chart``'s JSON answer into a :class:`ValidationReport`.

    An ``implicit-aggregate`` warning counts as an error, since a chart whose rows Flint would
    merge draws a different number than the result holds.
    """
    errors = [_message(entry) for entry in _entries(payload.get("errors"))]
    warnings: list[str] = []
    for entry in _entries(payload.get("warnings")):
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
    A connection to ``flint-chart-mcp``, used as the ``validator`` of :func:`show_chart`.

    Start one per process and share it: it is an async context manager that spawns the sidecar
    (or connects to it over HTTP) on entry and stops it on exit.

    Example:
        .. code-block:: python

            async with FlintSidecar() as sidecar:
                receipt = await show_chart(session, ..., validator=sidecar)

    Args:
        command: The command that starts the sidecar on stdio. By default ``npx`` runs the
            ``flint-chart-mcp`` release the mapping is pinned to.
        url: The sidecar's streamable HTTP endpoint, such as ``http://flint:3000/mcp``, in place
            of starting one.
        timeout: Seconds to wait for one validation.
    """

    def __init__(
        self,
        command: Sequence[str] = DEFAULT_SIDECAR_COMMAND,
        *,
        url: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._command = tuple(command)
        self._url = url
        self._timeout = timeout
        self._stack: contextlib.AsyncExitStack | None = None
        self._session: ClientSession | None = None

    async def __aenter__(self) -> Self:
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            from mcp.client.streamable_http import streamable_http_client
        except ImportError as error:  # pragma: no cover - depends on the install
            raise ImportError(
                "FlintSidecar needs the validate extra: "
                "pip install 's-layer-flint-charts[validate]'"
            ) from error
        stack = contextlib.AsyncExitStack()
        try:
            if self._url is not None:
                read, write = await stack.enter_async_context(streamable_http_client(self._url))
            else:
                command, *args = self._command
                read, write = await stack.enter_async_context(
                    stdio_client(StdioServerParameters(command=command, args=args))
                )
            session = await stack.enter_async_context(
                ClientSession(read, write, read_timeout_seconds=self._timeout)
            )
            await session.initialize()
        except BaseException:
            await stack.aclose()
            raise
        self._stack, self._session = stack, session
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        stack, self._stack, self._session = self._stack, None, None
        if stack is not None:
            await stack.aclose()

    async def validate(self, flint_input: Mapping[str, object]) -> ValidationReport:
        """
        Ask Flint whether it can draw ``flint_input``, as the Vega-Lite backend would.

        Raises:
            SidecarError: The sidecar is not started, or did not answer with a report.
        """
        if self._session is None:
            raise SidecarError("the Flint sidecar is not started; use `async with FlintSidecar()`")
        result = await self._session.call_tool(
            "validate_chart", {**flint_input, "backend": "vegalite"}
        )
        texts = [
            text
            for block in result.content
            if isinstance(text := getattr(block, "text", None), str)
        ]
        if result.is_error:
            raise SidecarError(f"validate_chart failed: {' '.join(texts)}")
        for text in texts:
            with contextlib.suppress(ValueError):
                payload: object = json.loads(text)
                if isinstance(payload, dict) and "valid" in payload:
                    return report_from_result(cast("dict[str, object]", payload))
        raise SidecarError(f"validate_chart answered without a report: {' '.join(texts)[:200]}")
