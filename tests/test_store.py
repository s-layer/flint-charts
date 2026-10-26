"""The per-conversation store of results and charts."""

from __future__ import annotations

import datetime as dt

from s_layer_flint_charts import (
    ChartRows,
    ChartSession,
    ChartStore,
    Column,
    FieldType,
    Metric,
    StoredChart,
    StoredResult,
)


def result(session: ChartSession) -> StoredResult:
    return StoredResult(
        result_id=session.new_result_id(),
        view="sales",
        columns={},
        rows=ChartRows(rows=[], fields={}, capped=False, total_rows=0),
        queried_at=dt.datetime(2024, 1, 1, tzinfo=dt.UTC),
    )


def chart(session: ChartSession) -> StoredChart:
    return StoredChart(chart_id=session.new_chart_id(), result_id="r_x", rows=b"[]")


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_ids_are_prefixed_and_distinct() -> None:
    session = ChartSession()
    results = {session.new_result_id() for _ in range(100)}
    charts = {session.new_chart_id() for _ in range(100)}
    assert len(results) == len(charts) == 100
    assert all(id_.startswith("r_") and len(id_) > 10 for id_ in results)
    assert all(id_.startswith("c_") and len(id_) > 10 for id_ in charts)


def test_a_session_keeps_only_its_newest_results_and_charts() -> None:
    session = ChartSession(max_results=2, max_charts=2)
    first, second, third = result(session), result(session), result(session)
    for stored in (first, second, third):
        session.add_result(stored)
    assert session.result(first.result_id) is None
    assert session.result(third.result_id) is third
    charts = [chart(session) for _ in range(3)]
    for stored in charts:
        session.add_chart(stored)
    assert [session.chart(c.chart_id) for c in charts] == [None, charts[1], charts[2]]


def test_an_unknown_id_is_none() -> None:
    session = ChartSession()
    assert session.result("r_nope") is None
    assert session.chart("c_nope") is None


def test_sessions_are_kept_apart() -> None:
    store = ChartStore()
    mine, theirs = store.session("a"), store.session("b")
    stored = result(mine)
    mine.add_result(stored)
    assert store.session("a") is mine
    assert theirs.result(stored.result_id) is None


def test_get_never_makes_a_session() -> None:
    store = ChartStore()
    assert store.get("a") is None
    made = store.session("a")
    assert store.get("a") is made


def test_unused_sessions_expire_after_the_ttl() -> None:
    clock = Clock()
    store = ChartStore(ttl=10, clock=clock)
    kept, dropped = store.session("kept"), store.session("dropped")
    clock.now = 8
    assert store.session("kept") is kept  # used again, so its clock restarts
    clock.now = 11
    assert store.get("dropped") is None
    assert store.get("kept") is kept
    clock.now = 19
    assert store.get("kept") is None
    assert store.session("dropped") is not dropped


def test_the_least_recently_used_session_goes_past_the_limit() -> None:
    store = ChartStore(max_sessions=2)
    a = store.session("a")
    store.session("b")
    store.session("a")
    store.session("c")
    assert store.get("b") is None
    assert store.get("a") is a


def test_store_limits_reach_its_sessions() -> None:
    session = ChartStore(max_results=1).session("a")
    first, second = result(session), result(session)
    session.add_result(first)
    session.add_result(second)
    assert session.result(first.result_id) is None


def test_a_column_is_a_metric_when_it_has_additivity() -> None:
    field = FieldType(semantic_type="Amount")
    assert Column(name="revenue", field_type=field, metric=Metric()).kind == "metric"
    assert Column(name="region", field_type=field).kind == "dimension"
