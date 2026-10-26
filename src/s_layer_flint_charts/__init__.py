"""
Semantic-layer-aware Flint charts for agents.

Maps S-LAYER semantic formats to Flint semantic types and annotations, turns query results into
the rows a chart draws, and refuses charts that would merge rows.
"""

from s_layer_flint_charts._grain import (
    PIE_CHART_TYPES,
    ROW_MARK_CHART_TYPES,
    STACKING_CHART_TYPES,
    ChartRequest,
    GrainCheck,
    Metric,
    check_grain,
)
from s_layer_flint_charts._mapping import (
    FLINT_SEMANTIC_TYPES,
    FLINT_VERSION,
    FieldType,
    Grain,
    ValueForm,
    field_display_names,
    fit_to_values,
    map_field,
    semantic_types,
)
from s_layer_flint_charts._rows import (
    DEFAULT_ROW_CAP,
    ChartRows,
    DuplicateColumnError,
    UnsupportedColumnError,
    chart_rows,
)

__all__ = [
    "DEFAULT_ROW_CAP",
    "FLINT_SEMANTIC_TYPES",
    "FLINT_VERSION",
    "PIE_CHART_TYPES",
    "ROW_MARK_CHART_TYPES",
    "STACKING_CHART_TYPES",
    "ChartRequest",
    "ChartRows",
    "DuplicateColumnError",
    "FieldType",
    "GrainCheck",
    "Grain",
    "Metric",
    "UnsupportedColumnError",
    "ValueForm",
    "chart_rows",
    "check_grain",
    "field_display_names",
    "fit_to_values",
    "map_field",
    "semantic_types",
]
