"""
Semantic-layer-aware Flint charts for agents.

Maps S-LAYER semantic formats to Flint semantic types and annotations, turns query results into
the rows a chart draws, refuses charts that would merge rows, and keeps results and charts for
the tools and the browser. The HTTP routes are in :mod:`s_layer_flint_charts.server` and the
Pydantic AI toolset in :mod:`s_layer_flint_charts.pydantic_ai`.
"""

from s_layer_flint_charts._charts import (
    CHART_TYPES,
    ChartReceipt,
    ChartValidator,
    ValidationReport,
    assemble_chart,
    chart_rows_url,
    default_interactions,
    show_chart,
)
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
    percent_points,
    semantic_types,
)
from s_layer_flint_charts._query import Fetch, result_columns, run_query, store_result, summarize
from s_layer_flint_charts._rows import (
    DEFAULT_ROW_CAP,
    ChartRows,
    DuplicateColumnError,
    UnsupportedColumnError,
    chart_rows,
)
from s_layer_flint_charts._sidecar import (
    DEFAULT_SIDECAR_COMMAND,
    FLINT_MCP_VERSION,
    FlintSidecar,
    SidecarError,
    report_from_result,
)
from s_layer_flint_charts._store import ChartSession, ChartStore, Column, StoredChart, StoredResult

__all__ = [
    "CHART_TYPES",
    "DEFAULT_ROW_CAP",
    "DEFAULT_SIDECAR_COMMAND",
    "FLINT_MCP_VERSION",
    "FLINT_SEMANTIC_TYPES",
    "FLINT_VERSION",
    "PIE_CHART_TYPES",
    "ROW_MARK_CHART_TYPES",
    "STACKING_CHART_TYPES",
    "ChartReceipt",
    "ChartRequest",
    "ChartRows",
    "ChartSession",
    "ChartStore",
    "ChartValidator",
    "Column",
    "DuplicateColumnError",
    "Fetch",
    "FieldType",
    "FlintSidecar",
    "Grain",
    "GrainCheck",
    "Metric",
    "SidecarError",
    "StoredChart",
    "StoredResult",
    "UnsupportedColumnError",
    "ValidationReport",
    "ValueForm",
    "assemble_chart",
    "chart_rows",
    "chart_rows_url",
    "check_grain",
    "default_interactions",
    "field_display_names",
    "fit_to_values",
    "map_field",
    "percent_points",
    "report_from_result",
    "result_columns",
    "run_query",
    "semantic_types",
    "show_chart",
    "store_result",
    "summarize",
]
