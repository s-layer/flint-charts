"""
The route the browser fetches a chart's rows from. Needs the ``server`` extra.

The model never sees a chart's rows: its ``show_chart`` result points ``data.url`` here, and
the browser's chart component fetches them. The route is scoped to the conversation the request
belongs to, which the app decides with ``session_of``.
"""

from __future__ import annotations

import gzip
import importlib
import inspect
from typing import TYPE_CHECKING, TypeAlias

try:
    from starlette.responses import Response
    from starlette.routing import Route
except ImportError as error:  # pragma: no cover - depends on the install
    raise ImportError(
        "the chart routes need the server extra: pip install 's-layer-flint-charts[server]'"
    ) from error


if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.requests import Request

    from s_layer_flint_charts._store import ChartStore

__all__ = ["SessionOf", "chart_routes", "encode_body"]

SessionOf: TypeAlias = "Callable[[Request], str | None | Awaitable[str | None]]"
"""Says which conversation a request belongs to, or ``None`` when it belongs to none."""

_MIN_COMPRESSED = 1024
"""Bodies smaller than this go out as they are; compressing them gains nothing."""


def _zstd_compress() -> Callable[[bytes], bytes] | None:
    # The standard library has zstd from Python 3.14; backports.zstd is the same module before.
    for module in ("compression.zstd", "backports.zstd"):
        try:
            return importlib.import_module(module).compress
        except ImportError:
            continue
    return None  # pragma: no cover - the server extra installs the backport


_ZSTD_COMPRESS = _zstd_compress()

_HEADERS = {"Cache-Control": "private, max-age=3600", "Vary": "Accept-Encoding"}


def chart_routes(store: ChartStore, session_of: SessionOf) -> list[Route]:
    """
    ``GET /charts/{chart_id}/rows``, to mount in the app where ``show_chart``'s URLs point.

    The model's ``show_chart`` result carries the chart's Flint input with ``data.url`` in
    place of its rows; this route answers that URL with the rows, a JSON array. It answers 404
    when the id is unknown, expired, or belongs to another conversation.

    Example:
        .. code-block:: python

            app = Starlette(routes=[Mount("/flint", routes=chart_routes(store, session_of))])

    Args:
        store: The store the tools keep results and charts in.
        session_of: The conversation a request belongs to, such as one read from a signed
            cookie. It may be async.

    Returns:
        The routes.
    """

    async def rows(request: Request) -> Response:
        session_id = session_of(request)
        if inspect.isawaitable(session_id):
            session_id = await session_id
        session = None if session_id is None else store.get(session_id)
        chart = session.chart(request.path_params["chart_id"]) if session else None
        if chart is None:
            return Response(status_code=404)
        return _json(request, chart.rows)

    return [Route("/charts/{chart_id}/rows", rows, methods=["GET"])]


def _json(request: Request, body: bytes) -> Response:
    content, encoding = encode_body(body, request.headers.get("accept-encoding", ""))
    headers = dict(_HEADERS)
    if encoding is not None:
        headers["Content-Encoding"] = encoding
    return Response(content, media_type="application/json", headers=headers)


def encode_body(body: bytes, accept_encoding: str) -> tuple[bytes, str | None]:
    """
    Compress a body with the best encoding the client accepts: zstd, then gzip.

    zstd is offered only where it is installed (Python 3.14, or ``backports.zstd``).

    Returns:
        The body to send and its ``Content-Encoding``, or ``None`` when it goes out as it is.
    """
    if len(body) < _MIN_COMPRESSED:
        return body, None
    accepted = _accepted(accept_encoding)
    if _ZSTD_COMPRESS is not None and "zstd" in accepted:
        return _ZSTD_COMPRESS(body), "zstd"
    if "gzip" in accepted:
        return gzip.compress(body, compresslevel=6), "gzip"
    return body, None


def _accepted(header: str) -> set[str]:
    accepted: set[str] = set()
    for part in header.split(","):
        name, _, params = part.strip().partition(";")
        quality = 1.0
        for param in params.split(";"):
            key, _, value = param.strip().partition("=")
            if key == "q":
                try:
                    quality = float(value)
                except ValueError:
                    quality = 0.0
        if name and quality > 0:
            accepted.add(name.strip().lower())
    return accepted
