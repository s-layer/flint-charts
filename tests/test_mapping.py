"""SemanticFormat to Flint type mapping."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pyarrow as pa
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from s_layer_semantic_formats import KINDS, NUMERIC_KINDS, Additivity, SLayerBlock

from s_layer_flint_charts import (
    CHART_TYPES,
    FLINT_MCP_VERSION,
    FLINT_SEMANTIC_TYPES,
    FLINT_VERSION,
    FieldType,
    Grain,
    default_interactions,
    field_display_names,
    fit_to_values,
    map_field,
    percent_points,
    semantic_types,
)

PIN_FILE = Path(__file__).parent.parent / "ts" / "test" / "flint-pin.json"


def block(value: dict[str, Any], **rest: Any) -> SLayerBlock:
    return SLayerBlock.model_validate({"value": value, **rest})


ANY = pa.float64()  # the Arrow type is ignored whenever there is a block


class TestBlockMapping:
    """One case per row of the mapping table in the design doc."""

    @pytest.mark.parametrize(
        ("value", "rest", "expected"),
        [
            pytest.param(
                {"kind": "currency", "currency": "USD"},
                {},
                FieldType(semantic_type="Amount", unit="USD"),
                id="currency-unstated-is-amount",
            ),
            pytest.param(
                {"kind": "currency", "currency": "EUR"},
                {"aggregation": {"additivity": "additive"}},
                FieldType(semantic_type="Amount", unit="EUR"),
                id="currency-additive",
            ),
            pytest.param(
                {"kind": "currency", "currency": "GBP"},
                {"aggregation": {"additivity": "semi_additive", "by": ["snapshot_date"]}},
                FieldType(semantic_type="Amount", unit="GBP"),
                id="currency-semi-additive",
            ),
            pytest.param(
                {"kind": "currency", "currency": "USD"},
                {"aggregation": {"additivity": "non_additive"}},
                FieldType(semantic_type="Price", unit="USD"),
                id="currency-non-additive-is-price",
            ),
            pytest.param({"kind": "count"}, {}, FieldType(semantic_type="Count"), id="count"),
            pytest.param({"kind": "number"}, {}, FieldType(semantic_type="Number"), id="number"),
            pytest.param(
                {"kind": "number", "unit": "Cel"},
                {},
                FieldType(semantic_type="Number", unit="Cel"),
                id="number-with-unit",
            ),
            pytest.param(
                {"kind": "percentage"},
                {},
                FieldType(semantic_type="Percentage", intrinsic_domain=(0, 1)),
                id="percentage-fraction",
            ),
            pytest.param(
                {"kind": "percentage", "scale": "percent"},
                {},
                FieldType(
                    semantic_type="Percentage",
                    intrinsic_domain=(0, 1),
                    value_form="percent_to_fraction",
                ),
                id="percentage-percent-sent-as-fraction",
            ),
            pytest.param(
                {"kind": "duration", "unit": "h"},
                {},
                FieldType(semantic_type="Duration", unit="hours"),
                id="duration",
            ),
            pytest.param(
                {"kind": "bytes", "unit": "GiB"},
                {},
                FieldType(semantic_type="Quantity", unit="GiB"),
                id="bytes",
            ),
            pytest.param(
                {"kind": "bytes"},
                {},
                FieldType(semantic_type="Quantity", unit="B"),
                id="bytes-default-unit",
            ),
            pytest.param(
                {"kind": "quantity", "unit": "kg"},
                {},
                FieldType(semantic_type="Quantity", unit="kg"),
                id="quantity",
            ),
            pytest.param(
                {"kind": "score", "range": [1, 5]},
                {},
                FieldType(semantic_type="Score", intrinsic_domain=(1, 5)),
                id="score",
            ),
            pytest.param(
                {"kind": "category"}, {}, FieldType(semantic_type="Category"), id="category"
            ),
            pytest.param(
                {"kind": "category", "order": ["Low", "Medium", "High"]},
                {},
                FieldType(semantic_type="Category", sort_order=("Low", "Medium", "High")),
                id="category-ordered",
            ),
            pytest.param({"kind": "boolean"}, {}, FieldType(semantic_type="Boolean"), id="boolean"),
            pytest.param(
                {"kind": "identifier"}, {}, FieldType(semantic_type="ID"), id="identifier"
            ),
            pytest.param(
                {"kind": "date"},
                {},
                FieldType(semantic_type="Date", value_form="date"),
                id="date-no-grain",
            ),
            pytest.param(
                {"kind": "datetime"},
                {},
                FieldType(semantic_type="DateTime", value_form="datetime"),
                id="datetime-no-grain",
            ),
        ],
    )
    def test_kind(self, value: dict[str, Any], rest: dict[str, Any], expected: FieldType) -> None:
        assert map_field(block(value, **rest), ANY) == expected

    @pytest.mark.parametrize(
        ("level", "semantic_type"),
        [
            ("country", "Country"),
            ("region", "Region"),
            ("state", "State"),
            ("city", "City"),
            ("postal_code", "ZipCode"),
            ("latitude", "Latitude"),
            ("longitude", "Longitude"),
        ],
    )
    def test_geo_level(self, level: str, semantic_type: str) -> None:
        mapped = map_field(block({"kind": "geo", "level": level}), pa.string())
        assert mapped == FieldType(semantic_type=semantic_type)

    @pytest.mark.parametrize(
        ("unit", "flint_unit"),
        [("ms", "ms"), ("s", "seconds"), ("min", "minutes"), ("h", "hours"), ("d", "days")],
    )
    def test_duration_unit_spelled_for_flint(self, unit: str, flint_unit: str) -> None:
        mapped = map_field(block({"kind": "duration", "unit": unit}), pa.int64())
        assert mapped.unit == flint_unit


class TestTemporalGrain:
    @pytest.mark.parametrize(
        ("kind", "grain", "semantic_type", "value_form"),
        [
            ("date", "year", "Year", "year"),
            ("date", "quarter", "YearQuarter", "year_quarter"),
            ("date", "month", "YearMonth", "year_month"),
            # A week is its Monday on a date axis, not Flint's YearWeek label sequence.
            ("date", "week", "Date", "date"),
            ("date", "day", "Date", "date"),
            ("datetime", "year", "Year", "year"),
            ("datetime", "quarter", "YearQuarter", "year_quarter"),
            ("datetime", "month", "YearMonth", "year_month"),
            ("datetime", "week", "Date", "date"),
            ("datetime", "day", "Date", "date"),
            ("datetime", "hour", "DateTime", "datetime"),
            ("datetime", "minute", "DateTime", "datetime"),
            ("datetime", "second", "DateTime", "datetime"),
        ],
    )
    def test_declared_grain(
        self, kind: str, grain: str, semantic_type: str, value_form: str
    ) -> None:
        mapped = map_field(block({"kind": kind}, time={"grain": grain}), pa.date32())
        assert (mapped.semantic_type, mapped.value_form) == (semantic_type, value_form)

    @pytest.mark.parametrize("grain", ["hour", "minute", "second"])
    def test_a_date_stays_a_date_at_sub_day_grain(self, grain: Grain) -> None:
        # A date has no time of day, so it never becomes a continuous DateTime axis.
        expected = ("Date", "date")
        declared = map_field(block({"kind": "date"}), pa.date32(), grain=grain)
        undeclared = map_field(None, pa.date32(), grain=grain)
        assert (declared.semantic_type, declared.value_form) == expected
        assert (undeclared.semantic_type, undeclared.value_form) == expected

    def test_never_a_cyclic_type(self) -> None:
        # Flint's Month, Quarter, Day and Hour are cycles (Jan..Dec), not points on a timeline.
        cyclic = {"Month", "Quarter", "Week", "Day", "Hour", "YearWeek"}
        assert not cyclic & FLINT_SEMANTIC_TYPES

    def test_query_grain_wins_over_declared_grain(self) -> None:
        day_grain = block({"kind": "date"}, time={"grain": "day"})
        assert map_field(day_grain, pa.date32()).semantic_type == "Date"
        assert map_field(day_grain, pa.date32(), grain="month").semantic_type == "YearMonth"
        assert map_field(day_grain, pa.date32(), grain="quarter").semantic_type == "YearQuarter"

    def test_query_grain_applies_to_an_undeclared_temporal_column(self) -> None:
        mapped = map_field(None, pa.timestamp("us"), grain="month")
        assert (mapped.semantic_type, mapped.value_form, mapped.fallback) == (
            "YearMonth",
            "year_month",
            True,
        )


class TestAdditivity:
    def test_definition_additivity_used_when_block_is_silent(self) -> None:
        silent = block({"kind": "currency", "currency": "USD"})
        assert map_field(silent, ANY, additivity="non_additive").semantic_type == "Price"
        assert map_field(silent, ANY, additivity="semi_additive").semantic_type == "Amount"

    def test_block_additivity_wins_over_definition(self) -> None:
        stated = block(
            {"kind": "currency", "currency": "USD"}, aggregation={"additivity": "additive"}
        )
        assert map_field(stated, ANY, additivity="non_additive").semantic_type == "Amount"


class TestFitToValues:
    PERCENTAGE = FieldType(
        semantic_type="Percentage", intrinsic_domain=(0, 1), display_name="Margin"
    )

    @pytest.mark.parametrize(("low", "high"), [(0, 1), (0.12, 0.87), (0, 0), (1, 1)])
    def test_percentage_inside_unit_range_is_unchanged(self, low: float, high: float) -> None:
        assert fit_to_values(self.PERCENTAGE, low, high) is self.PERCENTAGE

    @pytest.mark.parametrize(
        ("low", "high", "domain"),
        [
            (-0.12, 1.8, (-0.12, 1.8)),
            (-0.3, 0.4, (-0.3, 1)),
            (0.2, 2.5, (0, 2.5)),
            (-0.5, -0.1, (-0.5, 1)),
        ],
    )
    def test_percentage_outside_unit_range_becomes_a_change(
        self, low: float, high: float, domain: tuple[float, float]
    ) -> None:
        fitted = fit_to_values(self.PERCENTAGE, low, high)
        assert fitted == FieldType(
            semantic_type="PercentageChange", intrinsic_domain=domain, display_name="Margin"
        )
        assert fitted.intrinsic_domain is not None
        assert fitted.intrinsic_domain[0] <= low
        assert fitted.intrinsic_domain[1] >= high

    @pytest.mark.parametrize(
        "field",
        [
            FieldType(semantic_type="Amount", unit="USD"),
            FieldType(semantic_type="Score", intrinsic_domain=(1, 5)),
            FieldType(semantic_type="Number"),
        ],
    )
    def test_other_types_are_unchanged(self, field: FieldType) -> None:
        assert fit_to_values(field, -10, 10) is field


class TestFallback:
    """A column with no block is typed from its Arrow type and reported as a fallback."""

    @pytest.mark.parametrize(
        ("arrow_type", "aggregation", "expected"),
        [
            (pa.date32(), None, FieldType(semantic_type="Date", value_form="date")),
            (pa.date64(), None, FieldType(semantic_type="Date", value_form="date")),
            (
                pa.timestamp("us", tz="UTC"),
                None,
                FieldType(semantic_type="DateTime", value_form="datetime"),
            ),
            (pa.int64(), "count", FieldType(semantic_type="Count")),
            (pa.int32(), "COUNT_DISTINCT", FieldType(semantic_type="Count")),
            (pa.int64(), "sum", FieldType(semantic_type="Number")),
            (pa.int64(), None, FieldType(semantic_type="Number")),
            # A count is a whole number: an averaged count is not a Count.
            (pa.float64(), "count", FieldType(semantic_type="Number")),
            (pa.decimal128(18, 2), None, FieldType(semantic_type="Number")),
            (pa.string(), None, FieldType(semantic_type="Category")),
            (pa.large_string(), None, FieldType(semantic_type="Category")),
            (pa.bool_(), None, FieldType(semantic_type="Boolean")),
            (pa.binary(), None, FieldType(semantic_type="Category")),
        ],
    )
    def test_arrow_type(
        self, arrow_type: pa.DataType, aggregation: str | None, expected: FieldType
    ) -> None:
        mapped = map_field(None, arrow_type, aggregation=aggregation)
        assert mapped == FieldType(
            semantic_type=expected.semantic_type, value_form=expected.value_form, fallback=True
        )

    def test_block_is_not_a_fallback(self) -> None:
        assert not map_field(block({"kind": "count"}), pa.int64()).fallback

    def test_block_wins_over_arrow_type(self) -> None:
        # An integer column declared as currency is money, not a count or a number.
        mapped = map_field(block({"kind": "currency", "currency": "JPY"}), pa.int64())
        assert mapped.semantic_type == "Amount"


class TestDisplayName:
    def test_platform_label_wins_over_block_label(self) -> None:
        labelled = block({"kind": "count"}, label="Orders (block)")
        assert map_field(labelled, ANY, label="Orders").display_name == "Orders"

    def test_block_label_when_platform_has_none(self) -> None:
        labelled = block({"kind": "count"}, label="Orders (block)")
        assert map_field(labelled, ANY).display_name == "Orders (block)"

    def test_fallback_keeps_platform_label(self) -> None:
        assert map_field(None, pa.int64(), label="Orders").display_name == "Orders"


class TestFlintInput:
    def test_bare_type_when_nothing_to_annotate(self) -> None:
        assert FieldType(semantic_type="Count").flint_annotation() == "Count"

    def test_annotation_carries_only_set_keys(self) -> None:
        fields = {
            "revenue": map_field(block({"kind": "currency", "currency": "USD"}), ANY),
            "margin": map_field(block({"kind": "percentage"}), ANY),
            "rating": map_field(block({"kind": "score", "range": [1, 5]}), ANY),
            "size": map_field(block({"kind": "category", "order": ["S", "M", "L"]}), ANY),
            "orders": map_field(block({"kind": "count"}), ANY, label="Orders"),
        }
        assert semantic_types(fields) == {
            "revenue": {"semanticType": "Amount", "unit": "USD"},
            "margin": {"semanticType": "Percentage", "intrinsicDomain": [0, 1]},
            "rating": {"semanticType": "Score", "intrinsicDomain": [1, 5]},
            "size": {"semanticType": "Category", "sortOrder": ["S", "M", "L"]},
            "orders": "Count",
        }
        assert field_display_names(fields) == {"orders": "Orders"}

    def test_score_domain_is_json_numbers(self) -> None:
        mapped = map_field(block({"kind": "score", "range": [0, 10.5]}), ANY)
        assert json.loads(json.dumps(mapped.flint_annotation())) == {
            "semanticType": "Score",
            "intrinsicDomain": [0, 10.5],
        }


ARROW_TYPES = st.sampled_from(
    [
        pa.int64(),
        pa.float64(),
        pa.decimal128(18, 2),
        pa.string(),
        pa.bool_(),
        pa.date32(),
        pa.timestamp("us"),
        pa.binary(),
    ]
)
GRAINS = st.none() | st.sampled_from(
    ["second", "minute", "hour", "day", "week", "month", "quarter", "year"]
)


WORDS = st.text(st.characters(codec="utf-8", exclude_categories=["Cs"]), min_size=1, max_size=8)
ADDITIVITY = st.sampled_from(["additive", "semi_additive", "non_additive"])


@st.composite
def value_dicts(draw: st.DrawFn, kind: str) -> dict[str, Any]:
    """A valid ``value`` object of the given kind, with its optional keys drawn or left out."""
    value: dict[str, Any] = {"kind": kind}
    match kind:
        case "number":
            if draw(st.booleans()):
                value["unit"] = draw(WORDS)
        case "currency":
            value["currency"] = draw(st.from_regex(r"[A-Z]{3}", fullmatch=True))
        case "percentage":
            if draw(st.booleans()):
                value["scale"] = draw(st.sampled_from(["fraction", "percent"]))
        case "duration":
            value["unit"] = draw(st.sampled_from(["ms", "s", "min", "h", "d"]))
        case "bytes":
            if draw(st.booleans()):
                value["unit"] = draw(st.sampled_from(["B", "KB", "MiB", "GB", "TiB"]))
        case "quantity":
            value["unit"] = draw(WORDS)
        case "score":
            low = draw(st.floats(-1e6, 1e6, allow_nan=False))
            high = draw(st.floats(low, 2e6, allow_nan=False).filter(lambda x: x > low))
            value["range"] = [low, high]
        case "category":
            if draw(st.booleans()):
                value["order"] = draw(st.lists(WORDS, min_size=1, max_size=5, unique=True))
        case "geo":
            value["level"] = draw(
                st.sampled_from(
                    ["country", "region", "state", "city", "postal_code", "latitude", "longitude"]
                )
            )
        case _:
            pass
    return value


@st.composite
def blocks(draw: st.DrawFn) -> SLayerBlock:
    """Any valid block: every kind, with grain and additivity where the kind allows them."""
    kind = draw(st.sampled_from(KINDS))
    data: dict[str, Any] = {"value": draw(value_dicts(kind))}
    if kind == "date":
        if draw(st.booleans()):
            data["time"] = {
                "grain": draw(st.sampled_from(["day", "week", "month", "quarter", "year"]))
            }
    elif kind == "datetime":
        if draw(st.booleans()):
            data["time"] = {"grain": draw(GRAINS.filter(lambda g: g is not None))}
    elif kind in {"percentage", "score"}:
        if draw(st.booleans()):
            data["aggregation"] = {"additivity": "non_additive"}
    elif kind in {"number", "count", "currency", "duration", "bytes", "quantity"}:
        additivity = draw(st.none() | ADDITIVITY)
        if additivity == "semi_additive":
            data["aggregation"] = {"additivity": additivity, "by": ["snapshot_date"]}
        elif additivity is not None:
            data["aggregation"] = {"additivity": additivity}
    if draw(st.booleans()):
        data["label"] = draw(WORDS)
    return SLayerBlock.model_validate(data)


@settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
@given(
    mapped_block=blocks(),
    arrow_type=ARROW_TYPES,
    grain=GRAINS,
    additivity=st.none() | ADDITIVITY,
    aggregation=st.none() | st.sampled_from(["count", "sum", "avg"]),
)
def test_every_block_maps_to_a_pinned_flint_type(
    mapped_block: SLayerBlock,
    arrow_type: pa.DataType,
    grain: Grain | None,
    additivity: Additivity | None,
    aggregation: str | None,
) -> None:
    for mapped in (
        map_field(mapped_block, arrow_type, grain=grain, additivity=additivity),
        map_field(None, arrow_type, grain=grain, aggregation=aggregation),
    ):
        assert mapped.semantic_type in FLINT_SEMANTIC_TYPES
        annotation = mapped.flint_annotation()
        assert json.loads(json.dumps(annotation, allow_nan=False)) == annotation


@settings(max_examples=300)
@given(mapped_block=blocks(), grain=GRAINS)
def test_a_block_keeps_its_family(mapped_block: SLayerBlock, grain: Grain | None) -> None:
    """Measures stay measures, dimensions stay dimensions, only temporal kinds get a time axis."""
    mapped = map_field(mapped_block, pa.string(), grain=grain)
    temporal = {"Date", "DateTime", "Year", "YearMonth", "YearQuarter"}
    measures = {"Amount", "Price", "Count", "Number", "Percentage", "Duration", "Quantity", "Score"}
    if mapped_block.kind in {"date", "datetime"}:
        assert mapped.semantic_type in temporal
    elif mapped_block.kind in NUMERIC_KINDS:
        assert mapped.semantic_type in measures
        assert mapped.value_form in {"as_is", "percent_to_fraction"}
    else:
        assert mapped.semantic_type not in temporal | measures
        assert mapped.value_form == "as_is"


def expected_pin() -> dict[str, object]:
    """The Flint names the Python side emits: semantic types, chart types and their presets."""
    chart_types: dict[str, list[str]] = {}
    for chart_type in sorted(CHART_TYPES):
        spec = default_interactions(chart_type, has_color=True) or {"interactions": []}
        interactions = cast("list[dict[str, str]]", spec["interactions"])
        chart_types[chart_type] = [entry["type"] for entry in interactions]
    return {
        "flintVersion": FLINT_VERSION,
        "flintMcpVersion": FLINT_MCP_VERSION,
        "semanticTypes": sorted(FLINT_SEMANTIC_TYPES),
        "chartTypes": chart_types,
    }


def test_pin_file_matches_the_mapping() -> None:
    """
    The TS test suite checks this file against flint-chart's own registry.

    Regenerate it with ``uv run python -m tests.test_mapping``.
    """
    assert json.loads(PIN_FILE.read_text()) == expected_pin()


GROWTH = FieldType(semantic_type="PercentageChange", intrinsic_domain=(0, 3))
SHARE = FieldType(semantic_type="Percentage", intrinsic_domain=(0, 1))


def test_fractions_flint_would_read_as_points_go_out_as_points() -> None:
    # Flint 1.0.1 guesses percent points when under 80% of the values lie within [-1, 1].
    rows: list[dict[str, object]] = [{"growth": v} for v in (0.5, 1.8, 2.4, 3.0, 1.2)]
    sent, fields, points = percent_points(rows, {"growth": GROWTH})
    assert [row["growth"] for row in sent] == [50.0, 180.0, 240.0, 300.0, 120.0]
    assert fields["growth"].intrinsic_domain == (0, 300)
    assert points == frozenset({"growth"})


def test_fractions_flint_reads_as_fractions_are_unchanged() -> None:
    pairs = [(0.2, 0.5), (0.4, 3.0), (0.1, 0.4), (0.1, 0.4), (0.1, 0.4)]
    rows: list[dict[str, object]] = [{"share": v, "growth": g} for v, g in pairs]
    fields = {"share": SHARE, "growth": GROWTH}
    sent, sent_fields, points = percent_points(rows, fields)
    assert sent is rows
    assert sent_fields == fields
    assert points == frozenset()


def test_percent_points_skip_nulls_and_other_fields() -> None:
    rows: list[dict[str, object]] = [
        {"growth": 2.0, "revenue": 5},
        {"growth": None, "revenue": 7},
    ]
    fields = {"growth": GROWTH, "revenue": FieldType(semantic_type="Amount", unit="USD")}
    sent, _, points = percent_points(rows, fields)
    assert sent == [{"growth": 200.0, "revenue": 5}, {"growth": None, "revenue": 7}]
    assert points == frozenset({"growth"})


if __name__ == "__main__":
    PIN_FILE.write_text(json.dumps(expected_pin(), indent=2) + "\n")
