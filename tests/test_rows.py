"""Query result to JSON rows."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import orjson
import pyarrow as pa
import pytest
from hypothesis import given
from hypothesis import strategies as st

from s_layer_flint_charts import (
    DEFAULT_ROW_CAP,
    FieldType,
    UnsupportedColumnError,
    chart_rows,
)
from tests._arrow import array, chunked, table

PERCENT = FieldType(
    semantic_type="Percentage", intrinsic_domain=(0, 1), value_form="percent_to_fraction"
)
FRACTION = FieldType(semantic_type="Percentage", intrinsic_domain=(0, 1))


def single(column: pa.Array[Any], field: FieldType | None = None) -> list[object]:
    fields = {"c": field} if field is not None else {}
    result = chart_rows(table({"c": column}), fields)
    return [row["c"] for row in result.rows]


class TestValueForms:
    def test_percent_scale_becomes_fraction(self) -> None:
        assert single(array([12.5, 100, None]), PERCENT) == [0.125, 1.0, None]

    def test_fraction_scale_unchanged(self) -> None:
        assert single(array([0.25, 0.5]), FRACTION) == [0.25, 0.5]

    def test_year_from_date(self) -> None:
        values = array([dt.date(2024, 1, 1), dt.date(2025, 12, 31)])
        assert single(values, FieldType(semantic_type="Year", value_form="year")) == [2024, 2025]

    def test_year_month_from_timestamp(self) -> None:
        values = array([dt.datetime(2024, 1, 1), dt.datetime(2024, 11, 1)], pa.timestamp("us"))
        field = FieldType(semantic_type="YearMonth", value_form="year_month")
        assert single(values, field) == ["2024-01", "2024-11"]

    def test_year_quarter(self) -> None:
        values = array([dt.date(2024, 1, 1), dt.date(2024, 10, 1)])
        field = FieldType(semantic_type="YearQuarter", value_form="year_quarter")
        assert single(values, field) == ["2024-Q1", "2024-Q4"]

    def test_date_from_timestamp_drops_time(self) -> None:
        values = array([dt.datetime(2024, 3, 4, 0, 0)], pa.timestamp("ms"))
        field = FieldType(semantic_type="Date", value_form="date")
        assert single(values, field) == [dt.date(2024, 3, 4)]

    def test_zoned_timestamp_uses_local_date(self) -> None:
        # Midnight on 1 Feb in Tokyo is still 31 Jan in UTC.
        instant = dt.datetime(2024, 1, 31, 15, 0, tzinfo=dt.UTC)
        values = array([instant], pa.timestamp("us", tz="Asia/Tokyo"))
        month = FieldType(semantic_type="YearMonth", value_form="year_month")
        assert single(values, month) == ["2024-02"]
        day = FieldType(semantic_type="Date", value_form="date")
        assert single(values, day) == [dt.date(2024, 2, 1)]

    def test_period_already_text_left_alone(self) -> None:
        field = FieldType(semantic_type="YearMonth", value_form="year_month")
        assert single(array(["2024-01"]), field) == ["2024-01"]

    def test_json_dates_are_iso(self) -> None:
        values = array([dt.date(2024, 1, 15)])
        field = FieldType(semantic_type="Date", value_form="date")
        result = chart_rows(table({"d": values}), {"d": field})
        assert result.to_json() == b'[{"d":"2024-01-15"}]'

    def test_json_datetime_is_iso(self) -> None:
        values = array([dt.datetime(2024, 1, 15, 14, 30)], pa.timestamp("s"))
        field = FieldType(semantic_type="DateTime", value_form="datetime")
        result = chart_rows(table({"t": values}), {"t": field})
        assert result.to_json() == b'[{"t":"2024-01-15T14:30:00"}]'


class TestCasts:
    def test_decimal_becomes_float(self) -> None:
        values = array([Decimal("12.34"), None], pa.decimal128(10, 2))
        result = single(values)
        assert result == [12.34, None]
        assert isinstance(result[0], float)

    def test_dictionary_is_decoded(self) -> None:
        values = array(["a", "b", "a"], pa.dictionary(pa.int8(), pa.string()))
        assert single(values) == ["a", "b", "a"]

    def test_string_view_becomes_string(self) -> None:
        assert single(array(["x", None], pa.string_view())) == ["x", None]

    def test_safe_integers_stay_numbers(self) -> None:
        values = array([-(2**53 - 1), 2**53 - 1], pa.int64())
        assert single(values) == [-(2**53 - 1), 2**53 - 1]

    @pytest.mark.parametrize("big", [2**53, -(2**53), 2**63 - 1])
    def test_unsafe_integers_become_strings(self, big: int) -> None:
        values = array([1, big], pa.int64())
        assert single(values) == ["1", str(big)]

    def test_all_null_integer_column(self) -> None:
        assert single(array([None, None], pa.int64())) == [None, None]

    @pytest.mark.parametrize(
        "column",
        [
            array([b"x"], pa.binary()),
            array([dt.timedelta(seconds=1)], pa.duration("s")),
            array([[1, 2]], pa.list_(pa.int64())),
            array([{"a": 1}], pa.struct([("a", pa.int64())])),
        ],
        ids=["binary", "duration", "list", "struct"],
    )
    def test_unsupported_types_are_refused(self, column: pa.Array[Any]) -> None:
        with pytest.raises(UnsupportedColumnError, match="'c'"):
            single(column)

    @given(st.lists(st.one_of(st.none(), st.integers(min_value=-(2**63), max_value=2**63 - 1))))
    def test_integers_round_trip_exactly_through_json(self, values: list[int | None]) -> None:
        rows = chart_rows(table({"c": array(values, pa.int64())}), {})
        decoded = [row["c"] for row in orjson.loads(rows.to_json())]
        assert [None if v is None else int(v) for v in decoded] == values
        # A number in the JSON is exactly representable as a JavaScript number.
        assert all(not isinstance(v, int) or abs(v) <= 2**53 - 1 for v in decoded)


class TestCapAndFit:
    def test_cap_cuts_and_marks(self) -> None:
        result = chart_rows(table({"n": list(range(10))}), {}, cap=4)
        assert [row["n"] for row in result.rows] == [0, 1, 2, 3]
        assert result.capped
        assert result.total_rows == 10

    def test_at_cap_is_not_capped(self) -> None:
        result = chart_rows(table({"n": list(range(4))}), {}, cap=4)
        assert not result.capped
        assert len(result.rows) == 4

    def test_default_cap(self) -> None:
        assert DEFAULT_ROW_CAP == 5000

    def test_percentage_leaving_unit_range_becomes_change(self) -> None:
        result = chart_rows(table({"g": [-12.0, 180.0]}), {"g": PERCENT})
        assert result.fields["g"].semantic_type == "PercentageChange"
        assert result.fields["g"].intrinsic_domain == (-0.12, 1.8)

    def test_share_stays_percentage(self) -> None:
        result = chart_rows(table({"s": [10.0, 90.0]}), {"s": PERCENT})
        assert result.fields["s"] == PERCENT

    def test_fit_uses_only_kept_rows(self) -> None:
        # The out-of-range value is past the cap, so it is not drawn and does not widen.
        result = chart_rows(table({"s": [0.2, 0.3, 5.0]}), {"s": FRACTION}, cap=2)
        assert result.fields["s"] == FRACTION

    def test_all_null_percentage_unchanged(self) -> None:
        result = chart_rows(table({"s": array([None], pa.float64())}), {"s": PERCENT})
        assert result.fields["s"] == PERCENT

    def test_unmapped_columns_pass_through(self) -> None:
        result = chart_rows(
            table({"a": ["x"], "b": [1]}), {"a": FieldType(semantic_type="Category")}
        )
        assert result.rows == [{"a": "x", "b": 1}]
        assert set(result.fields) == {"a"}

    def test_chunked_columns(self) -> None:
        result = chart_rows(chunked({"n": [1, 2]}, {"n": [3]}), {})
        assert [row["n"] for row in result.rows] == [1, 2, 3]
