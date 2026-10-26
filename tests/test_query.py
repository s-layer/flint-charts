"""Running a query for a chart, keeping its result, and the summary the model gets."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from semolina import SemolinaSpecError
from semolina.spec import build_query

from s_layer_flint_charts import ChartSession, Metric, result_columns, run_query
from tests._arrow import table
from tests._views import Sales, monthly

if TYPE_CHECKING:
    import pyarrow as pa
    from semolina import Query

pytestmark = pytest.mark.anyio

SPEC: dict[str, Any] = {
    "metrics": ["revenue", "margin"],
    "dimensions": ["ordered_at__month", "region"],
}


class Recorder:
    """A fetch that answers from :func:`monthly` and remembers the query it ran."""

    def __init__(self) -> None:
        self.queries: list[Query] = []

    async def __call__(self, query: Query) -> pa.Table:
        self.queries.append(query)
        return monthly(query)


async def test_the_summary_describes_each_column() -> None:
    session = ChartSession()
    summary: Any = await run_query(session, Sales, SPEC, fetch=Recorder())
    assert summary["view"] == "analytics.sales"
    assert summary["rows"] == 6
    assert "capped" not in summary
    columns = {column["name"]: column for column in summary["columns"]}
    assert list(columns) == ["ordered_at__month", "region", "revenue", "margin"]
    assert columns["ordered_at__month"] == {
        "name": "ordered_at__month",
        "kind": "dimension",
        "type": "YearMonth",
        "min": "2024-01",
        "max": "2024-03",
        "distinct_values": 3,
        "sample_values": ["2024-01", "2024-02", "2024-03"],
    }
    assert columns["region"]["label"] == "Region"
    assert columns["revenue"] == {
        "name": "revenue",
        "kind": "metric",
        "type": "Amount",
        "label": "Revenue",
        "unit": "USD",
        "description": "Booked revenue",
        "min": 80.0,
        "max": 130.0,
    }
    # A 0-100 percentage is held as a fraction.
    assert (columns["margin"]["min"], columns["margin"]["max"]) == (0.115, 0.195)
    assert summary["sample_rows"][0] == {
        "ordered_at__month": "2024-01",
        "region": "EU",
        "revenue": 100.0,
        "margin": 0.12,
    }


async def test_the_result_is_kept_under_its_id() -> None:
    session = ChartSession()
    summary: Any = await run_query(session, Sales, SPEC, fetch=Recorder())
    stored = session.result(summary["result_id"])
    assert stored is not None
    assert stored.metrics == {
        "revenue": Metric(additivity="additive"),
        "margin": Metric(additivity="non_additive"),
    }
    assert len(stored.rows.rows) == 6


@pytest.mark.parametrize(("limit", "sent"), [(None, 4), (2, 2), (10, 4)])
async def test_the_query_asks_for_one_row_past_the_cap(limit: int | None, sent: int) -> None:
    fetch = Recorder()
    spec = SPEC if limit is None else {**SPEC, "limit": limit}
    await run_query(ChartSession(), Sales, spec, cap=3, fetch=fetch)
    assert fetch.queries[0].limit_value == sent


async def test_a_result_past_the_cap_is_marked_capped() -> None:
    summary: Any = await run_query(ChartSession(), Sales, SPEC, cap=5, fetch=Recorder())
    assert summary["rows"] == 5
    assert "more than 5 rows" in summary["capped"]


async def test_a_bad_spec_raises_for_its_author() -> None:
    with pytest.raises(SemolinaSpecError, match="profit"):
        await run_query(ChartSession(), Sales, {"metrics": ["profit"]}, fetch=Recorder())


def test_a_semi_additive_metric_is_not_summed_over_its_grained_snapshot_dimension() -> None:
    query = build_query(
        Sales, {"metrics": ["balance"], "dimensions": ["ordered_at__month", "region"]}
    )
    _, columns = result_columns(query, monthly(query))
    assert columns["balance"].metric == Metric(
        additivity="semi_additive", non_additive_by=frozenset({"ordered_at__month"})
    )
    assert columns["region"].metric is None


def test_columns_are_renamed_to_their_fields() -> None:
    query = build_query(Sales, {"metrics": ["revenue"], "dimensions": ["region"]})
    renamed, _ = result_columns(query, table({"Region": ["EU"], "REVENUE": [1.0]}))
    assert renamed.column_names == ["region", "revenue"]


def test_a_column_the_query_did_not_ask_for_is_refused() -> None:
    query = build_query(Sales, {"metrics": ["revenue"]})
    with pytest.raises(ValueError, match="'cost' is not a field of the query"):
        result_columns(query, table({"revenue": [1.0], "cost": [2.0]}))


def test_two_columns_for_one_field_are_refused() -> None:
    query = build_query(Sales, {"metrics": ["revenue"]})
    with pytest.raises(ValueError, match="more than one column"):
        result_columns(query, table({"revenue": [1.0], "REVENUE": [2.0]}))
