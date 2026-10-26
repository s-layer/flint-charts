"""The route the browser fetches a chart's rows from."""

from __future__ import annotations

import gzip
import importlib
from typing import TYPE_CHECKING

import orjson
import pytest
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.testclient import TestClient

from s_layer_flint_charts import ChartStore, StoredChart
from s_layer_flint_charts.server import chart_routes, encode_body

if TYPE_CHECKING:
    from starlette.requests import Request

ROWS = orjson.dumps([{"region": f"R{i}", "revenue": i * 1.5} for i in range(200)])


def app(store: ChartStore, *, session_async: bool = False) -> TestClient:
    def session_of(request: Request) -> str | None:
        return request.headers.get("x-conversation")

    async def session_of_async(request: Request) -> str | None:
        return session_of(request)

    routes = chart_routes(store, session_of_async if session_async else session_of)
    return TestClient(Starlette(routes=[Mount("/flint", routes=routes)]))


def chart(store: ChartStore, session_id: str = "a", rows: bytes = ROWS) -> str:
    session = store.session(session_id)
    stored = StoredChart(chart_id=session.new_chart_id(), result_id="r_x", rows=rows)
    session.add_chart(stored)
    return stored.chart_id


@pytest.mark.parametrize("session_async", [False, True])
def test_a_chart_answers_with_its_rows(session_async: bool) -> None:
    store = ChartStore()
    chart_id = chart(store)
    response = app(store, session_async=session_async).get(
        f"/flint/charts/{chart_id}/rows",
        headers={"x-conversation": "a", "accept-encoding": "identity"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == "private, max-age=3600"
    assert "content-encoding" not in response.headers
    assert response.content == ROWS


@pytest.mark.parametrize(
    "headers",
    [
        {},  # no conversation
        {"x-conversation": "b"},  # another conversation
    ],
)
def test_a_chart_is_hidden_from_other_conversations(headers: dict[str, str]) -> None:
    store = ChartStore()
    chart_id = chart(store)
    assert app(store).get(f"/flint/charts/{chart_id}/rows", headers=headers).status_code == 404


def test_an_unknown_chart_is_not_found() -> None:
    store = ChartStore()
    chart(store)
    response = app(store).get("/flint/charts/c_nope/rows", headers={"x-conversation": "a"})
    assert response.status_code == 404


def test_a_large_body_is_gzipped_for_a_client_without_zstd() -> None:
    store = ChartStore()
    chart_id = chart(store)
    response = app(store).get(
        f"/flint/charts/{chart_id}/rows",
        headers={"x-conversation": "a", "accept-encoding": "gzip"},
    )
    assert response.headers["content-encoding"] == "gzip"
    assert response.headers["vary"] == "Accept-Encoding"
    assert orjson.loads(response.content) == orjson.loads(ROWS)  # the client decompresses


def test_zstd_is_preferred() -> None:
    body, encoding = encode_body(ROWS, "gzip, deflate, br, zstd")
    assert encoding == "zstd"
    try:
        zstd = importlib.import_module("compression.zstd")
    except ImportError:  # before Python 3.14
        zstd = importlib.import_module("backports.zstd")
    assert zstd.decompress(body) == ROWS


@pytest.mark.parametrize(
    ("accept", "encoding"),
    [
        ("", None),
        ("identity", None),
        ("zstd;q=0, gzip", "gzip"),
        ("gzip;q=0", None),
        ("GZIP;q=0.5", "gzip"),
        ("gzip;q=oops", None),
    ],
)
def test_encoding_negotiation(accept: str, encoding: str | None) -> None:
    body, chosen = encode_body(ROWS, accept)
    assert chosen == encoding
    if encoding == "gzip":
        assert gzip.decompress(body) == ROWS
    if encoding is None:
        assert body == ROWS


def test_a_small_body_is_never_compressed() -> None:
    assert encode_body(b"[]", "zstd, gzip") == (b"[]", None)
