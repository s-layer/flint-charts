"""The grain guard."""

from __future__ import annotations

import pytest

from s_layer_flint_charts import ChartRequest, Metric, check_grain

ADDITIVE = Metric(additivity="additive")
RATIO = Metric(additivity="non_additive")
UNKNOWN = Metric()
BALANCE = Metric(additivity="semi_additive", non_additive_by=frozenset({"day"}))


def monthly_by_region(metric: str = "revenue") -> list[dict[str, object]]:
    return [
        {"month": month, "region": region, metric: value}
        for month, values in (("2024-01", (1, 2)), ("2024-02", (3, 4)))
        for region, value in zip(("EU", "US"), values, strict=True)
    ]


class TestEncodings:
    def test_unknown_column_refused(self) -> None:
        request = ChartRequest(chart_type="Line Chart", encodings={"x": "month", "y": "profit"})
        check = check_grain(monthly_by_region(), request, {"revenue": ADDITIVE})
        assert check.problems == ("profit is not a column of the result",)

    def test_aggregate_encoding_refused(self) -> None:
        request = ChartRequest(
            chart_type="Bar Chart",
            encodings={"x": "region", "y": {"field": "revenue", "aggregate": "sum"}},
        )
        check = check_grain(monthly_by_region(), request, {"revenue": ADDITIVE})
        assert not check.ok
        assert "aggregate" in check.problems[0]

    def test_encoding_object_field_is_read(self) -> None:
        request = ChartRequest(
            chart_type="Line Chart",
            encodings={"x": {"field": "month"}, "y": "revenue", "color": {"field": "region"}},
        )
        assert check_grain(monthly_by_region(), request, {"revenue": ADDITIVE}).ok


class TestUnplacedDimensions:
    def test_dimension_off_every_channel_refused(self) -> None:
        request = ChartRequest(chart_type="Line Chart", encodings={"x": "month", "y": "revenue"})
        check = check_grain(monthly_by_region(), request, {"revenue": ADDITIVE})
        assert check.problems == (
            "region has 2 values per month but is not on any channel; put it on a channel "
            "(such as color) or filter it to one value",
        )

    def test_dimension_with_one_value_per_mark_allowed(self) -> None:
        rows = [{"month": m, "region": "EU", "revenue": 1} for m in ("2024-01", "2024-02")]
        request = ChartRequest(chart_type="Line Chart", encodings={"x": "month", "y": "revenue"})
        assert check_grain(rows, request, {"revenue": ADDITIVE}).ok

    def test_dimension_functionally_dependent_allowed(self) -> None:
        # Each country sits in one region, so region adds no marks.
        rows = [
            {"country": "FR", "region": "EU", "revenue": 1},
            {"country": "DE", "region": "EU", "revenue": 2},
            {"country": "CA", "region": "NA", "revenue": 3},
        ]
        request = ChartRequest(chart_type="Bar Chart", encodings={"x": "country", "y": "revenue"})
        assert check_grain(rows, request, {"revenue": ADDITIVE}).ok

    def test_kpi_with_no_placed_dimension(self) -> None:
        request = ChartRequest(chart_type="KPI Card", encodings={"value": "revenue"})
        check = check_grain(monthly_by_region(), request, {"revenue": ADDITIVE})
        assert [p.split(" has ")[0] for p in check.problems] == ["month", "region"]
        assert check.problems[0].startswith("month has 2 values but")

    def test_metric_not_on_a_channel_is_fine(self) -> None:
        rows = [{"month": "2024-01", "revenue": 1, "orders": 2}]
        request = ChartRequest(chart_type="Line Chart", encodings={"x": "month", "y": "revenue"})
        assert check_grain(rows, request, {"revenue": ADDITIVE, "orders": ADDITIVE}).ok


class TestStacking:
    def test_ratio_stacked_by_region_refused(self) -> None:
        request = ChartRequest(
            chart_type="Bar Chart", encodings={"x": "month", "y": "margin", "color": "region"}
        )
        check = check_grain(monthly_by_region("margin"), request, {"margin": RATIO})
        assert check.problems == (
            "a Bar Chart sums margin across region, but it does not add up (a ratio, average or "
            "distinct count); use a Line Chart or a Grouped Bar Chart, or take color off",
        )

    @pytest.mark.parametrize("chart_type", ["Line Chart", "Grouped Bar Chart", "Scatter Plot"])
    def test_ratio_by_region_on_non_stacking_chart_allowed(self, chart_type: str) -> None:
        request = ChartRequest(
            chart_type=chart_type, encodings={"x": "month", "y": "margin", "color": "region"}
        )
        assert check_grain(monthly_by_region("margin"), request, {"margin": RATIO}).ok

    def test_layered_bars_do_not_stack(self) -> None:
        request = ChartRequest(
            chart_type="Stacked Bar Chart",
            encodings={"x": "month", "y": "margin", "color": "region"},
            chart_properties={"stackMode": "layered"},
        )
        assert check_grain(monthly_by_region("margin"), request, {"margin": RATIO}).ok

    def test_bar_colored_by_its_own_category_allowed(self) -> None:
        # One color per bar: nothing is stacked.
        rows = [{"region": r, "margin": 0.1} for r in ("EU", "US")]
        request = ChartRequest(
            chart_type="Bar Chart", encodings={"x": "region", "y": "margin", "color": "region"}
        )
        assert check_grain(rows, request, {"margin": RATIO}).ok

    def test_unknown_additivity_refused_when_stacked(self) -> None:
        request = ChartRequest(
            chart_type="Stacked Bar Chart",
            encodings={"x": "month", "y": "revenue", "color": "region"},
        )
        check = check_grain(monthly_by_region(), request, {"revenue": UNKNOWN})
        assert "additivity is not declared" in check.problems[0]

    def test_additive_stacked_allowed(self) -> None:
        request = ChartRequest(
            chart_type="Stacked Bar Chart",
            encodings={"x": "month", "y": "revenue", "color": "region"},
        )
        assert check_grain(monthly_by_region(), request, {"revenue": ADDITIVE}).ok

    def test_balance_stacked_along_snapshot_date_refused(self) -> None:
        rows = [{"account": "A", "day": d, "balance": 10} for d in ("2024-01-01", "2024-01-02")]
        request = ChartRequest(
            chart_type="Bar Chart", encodings={"x": "account", "y": "balance", "color": "day"}
        )
        check = check_grain(rows, request, {"balance": BALANCE})
        assert check.problems == (
            "a Bar Chart sums balance across day, but it cannot be summed over day; "
            "use a Line Chart or a Grouped Bar Chart, or take color off",
        )

    def test_balance_stacked_across_accounts_allowed(self) -> None:
        rows = [
            {"account": a, "day": d, "balance": 10}
            for a in ("A", "B")
            for d in ("2024-01-01", "2024-01-02")
        ]
        request = ChartRequest(
            chart_type="Area Chart", encodings={"x": "day", "y": "balance", "color": "account"}
        )
        assert check_grain(rows, request, {"balance": BALANCE}).ok

    @pytest.mark.parametrize("chart_type", ["Pie Chart", "Donut Chart"])
    def test_pie_of_ratio_refused_even_one_slice_per_color(self, chart_type: str) -> None:
        rows = [{"region": r, "margin": 0.1} for r in ("EU", "US")]
        request = ChartRequest(
            chart_type=chart_type, encodings={"size": "margin", "color": "region"}
        )
        check = check_grain(rows, request, {"margin": RATIO})
        assert not check.ok
        assert check.problems[0].startswith(f"a {chart_type} sums margin across region")

    def test_pie_of_additive_allowed(self) -> None:
        rows = [{"region": r, "revenue": 1} for r in ("EU", "US")]
        request = ChartRequest(
            chart_type="Pie Chart", encodings={"size": "revenue", "color": "region"}
        )
        assert check_grain(rows, request, {"revenue": ADDITIVE}).ok


class TestStackedAreaGaps:
    def gappy(self) -> list[dict[str, object]]:
        rows = monthly_by_region()
        return [row for row in rows if not (row["month"] == "2024-02" and row["region"] == "US")]

    def request(self, **properties: object) -> ChartRequest:
        return ChartRequest(
            chart_type="Area Chart",
            encodings={"x": "month", "y": "revenue", "color": "region"},
            chart_properties=properties,
        )

    def test_missing_points_of_additive_metric_become_zeros(self) -> None:
        check = check_grain(self.gappy(), self.request(), {"revenue": ADDITIVE})
        assert check.ok
        assert check.rows[-1] == {"month": "2024-02", "region": "US", "revenue": 0}
        assert len(check.rows) == 4
        assert "stackMode" not in check.chart_properties

    def test_filler_copies_unplaced_dimensions_and_blanks_other_metrics(self) -> None:
        rows = [{**row, "currency": "EUR", "orders": 5} for row in self.gappy()]
        check = check_grain(rows, self.request(), {"revenue": ADDITIVE, "orders": ADDITIVE})
        assert check.rows[-1] == {
            "month": "2024-02",
            "region": "US",
            "revenue": 0,
            "currency": "EUR",
            "orders": None,
        }

    def test_complete_area_unchanged(self) -> None:
        rows = monthly_by_region()
        check = check_grain(rows, self.request(), {"revenue": ADDITIVE})
        assert check.rows == rows

    def test_semi_additive_gaps_layer_instead(self) -> None:
        metrics = {"revenue": Metric(additivity="semi_additive", non_additive_by=frozenset({"x"}))}
        check = check_grain(self.gappy(), self.request(), metrics)
        assert check.ok
        assert check.chart_properties == {"stackMode": "layered"}
        assert len(check.rows) == 3

    def test_densify_over_cap_refused(self) -> None:
        check = check_grain(self.gappy(), self.request(), {"revenue": ADDITIVE}, cap=3)
        assert check.problems == (
            "filling the gaps in this stacked area would take 4 points, over the 3-row cap; "
            "filter it or use a coarser grain",
        )

    def test_layered_area_not_densified(self) -> None:
        check = check_grain(self.gappy(), self.request(stackMode="layered"), {"revenue": RATIO})
        assert check.ok
        assert len(check.rows) == 3

    def test_input_rows_not_mutated(self) -> None:
        rows = self.gappy()
        before = [dict(row) for row in rows]
        check_grain(rows, self.request(), {"revenue": ADDITIVE})
        assert rows == before


class TestReviewRound1:
    """Cases from the first review of the grain guard."""

    def test_repeated_placed_key_refused(self) -> None:
        rows = [{"m": "Jan", "r": 0.1}, {"m": "Jan", "r": 0.2}]
        request = ChartRequest(chart_type="Bar Chart", encodings={"x": "m", "y": "r"})
        check = check_grain(rows, request, {"r": RATIO})
        assert check.problems == (
            "2 rows share one m mark; the result is finer than the chart (for example months "
            "drawn as quarters), so query at the grain the chart shows",
        )

    def test_repeated_key_with_every_dimension_placed_refused(self) -> None:
        rows = [*monthly_by_region("margin"), {"month": "2024-01", "region": "EU", "margin": 9}]
        request = ChartRequest(
            chart_type="Line Chart", encodings={"x": "month", "y": "margin", "color": "region"}
        )
        check = check_grain(rows, request, {"margin": RATIO})
        assert check.problems[0].startswith("2 rows share one month and region mark")

    def test_empty_result_says_so(self) -> None:
        request = ChartRequest(chart_type="Line Chart", encodings={"x": "month", "y": "revenue"})
        check = check_grain([], request, {"revenue": ADDITIVE})
        assert check.problems == ("the query returned no rows, so there is nothing to chart",)

    def test_empty_stacked_area_of_metrics_does_not_crash(self) -> None:
        request = ChartRequest(
            chart_type="Area Chart", encodings={"y": "revenue", "color": "units"}
        )
        check = check_grain([], request, {"revenue": ADDITIVE, "units": ADDITIVE})
        assert not check.ok

    def test_encoded_metric_missing_from_rows_refused(self) -> None:
        request = ChartRequest(chart_type="Line Chart", encodings={"x": "month", "y": "profit"})
        rows = [{"month": "2024-01", "revenue": 1}]
        check = check_grain(rows, request, {"revenue": ADDITIVE, "profit": ADDITIVE})
        assert check.problems == ("profit is not a column of the result",)

    def test_metric_in_tooltip_is_not_stacked(self) -> None:
        rows = [{**row, "margin": 0.1} for row in monthly_by_region()]
        request = ChartRequest(
            chart_type="Stacked Bar Chart",
            encodings={"x": "month", "y": "revenue", "color": "region", "tooltip": "margin"},
        )
        assert check_grain(rows, request, {"revenue": ADDITIVE, "margin": RATIO}).ok

    def test_horizontal_stacked_bar_measure_on_x(self) -> None:
        request = ChartRequest(
            chart_type="Bar Chart", encodings={"y": "month", "x": "margin", "color": "region"}
        )
        check = check_grain(monthly_by_region("margin"), request, {"margin": RATIO})
        assert not check.ok

    def test_dimension_in_tooltip_does_not_split_a_stack(self) -> None:
        # Bars are positioned by x only; a tooltip dimension does not stop regions stacking.
        rows = [{**row, "label": f"{row['month']}/{row['region']}"} for row in monthly_by_region()]
        request = ChartRequest(
            chart_type="Bar Chart",
            encodings={"x": "month", "y": "revenue", "color": "region", "tooltip": "label"},
        )
        check = check_grain(rows, request, {"revenue": RATIO})
        assert not check.ok

    def test_area_fill_ignores_tooltip_dimension(self) -> None:
        rows = [{**row, "label": f"M{row['month']}"} for row in monthly_by_region()]
        request = ChartRequest(
            chart_type="Area Chart",
            encodings={"x": "month", "y": "revenue", "color": "region", "tooltip": "label"},
        )
        check = check_grain(rows, request, {"revenue": ADDITIVE})
        assert check.ok
        assert check.rows == rows

    def test_area_fill_copies_dimensions_from_the_same_x(self) -> None:
        rows = [
            {"month": m, "quarter": q, "region": r, "revenue": 1}
            for m, q in (("2024-03", "Q1"), ("2024-06", "Q2"))
            for r in ("EU", "US")
            if (m, r) != ("2024-06", "EU")
        ]
        request = ChartRequest(
            chart_type="Area Chart",
            encodings={"x": "month", "y": "revenue", "color": "region", "tooltip": "quarter"},
        )
        check = check_grain(rows, request, {"revenue": ADDITIVE})
        assert check.ok
        assert check.rows[-1] == {"month": "2024-06", "quarter": "Q2", "region": "EU", "revenue": 0}

    def test_area_fill_copies_unplaced_dimensions_from_the_same_color(self) -> None:
        rows = [
            {"month": m, "country": c, "region": r, "revenue": 1}
            for m in ("2024-01", "2024-02")
            for c, r in (("FR", "EU"), ("CA", "NA"))
            if (m, c) != ("2024-02", "CA")
        ]
        request = ChartRequest(
            chart_type="Area Chart", encodings={"x": "month", "y": "revenue", "color": "country"}
        )
        check = check_grain(rows, request, {"revenue": ADDITIVE})
        assert check.ok
        assert check.rows[-1] == {"month": "2024-02", "country": "CA", "region": "NA", "revenue": 0}

    def test_area_fill_per_facet(self) -> None:
        rows = [
            {"month": m, "region": r, "segment": s, "revenue": 1}
            for s in ("retail", "trade")
            for m in ("2024-01", "2024-02")
            for r in ("EU", "US")
            if (s, m, r) != ("trade", "2024-02", "US")
        ]
        request = ChartRequest(
            chart_type="Area Chart",
            encodings={"x": "month", "y": "revenue", "color": "region", "column": "segment"},
        )
        check = check_grain(rows, request, {"revenue": ADDITIVE})
        assert check.ok
        assert check.rows[-1] == {
            "month": "2024-02",
            "region": "US",
            "segment": "trade",
            "revenue": 0,
        }

    def test_dimension_only_in_tooltip_refused_with_its_own_words(self) -> None:
        request = ChartRequest(
            chart_type="Line Chart", encodings={"x": "month", "y": "revenue", "tooltip": "region"}
        )
        check = check_grain(monthly_by_region(), request, {"revenue": ADDITIVE})
        assert check.problems == (
            "region has 2 values per month but only labels the marks; put it on a channel "
            "(such as color) or filter it to one value",
        )
