"""
Semantic-layer-aware Flint charts for agents.

Maps S-LAYER semantic formats to Flint semantic types and annotations, so a chart's formatting,
zero baseline and default aggregation follow the semantic view's declarations.
"""

from s_layer_flint_charts._mapping import (
    FLINT_SEMANTIC_TYPES,
    FLINT_VERSION,
    FieldType,
    Grain,
    ValueForm,
    field_display_names,
    map_field,
    semantic_types,
)

__all__ = [
    "FLINT_SEMANTIC_TYPES",
    "FLINT_VERSION",
    "FieldType",
    "Grain",
    "ValueForm",
    "field_display_names",
    "map_field",
    "semantic_types",
]
