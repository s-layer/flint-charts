.. meta::
   :description: Semantic-layer-aware Flint charts for agents: types, grain guard and show_chart tool

====================
s-layer-flint-charts
====================

Semantic-layer-aware Flint charts for agents: types, grain guard and show_chart tool

Installation
------------

.. code-block:: bash

   pip install s-layer-flint-charts

Or with `uv <https://docs.astral.sh/uv/>`_:

.. code-block:: bash

   uv add s-layer-flint-charts

Quick Start
-----------

Map each result column to the Flint type its ``s_layer`` block declares:

.. code-block:: python

   import pyarrow as pa
   from s_layer_flint_charts import map_field, semantic_types
   from s_layer_semantic_formats import SLayerBlock

   block = SLayerBlock.model_validate({"value": {"kind": "currency", "currency": "USD"}})
   semantic_types({"revenue": map_field(block, pa.float64())})
   # {"revenue": {"semanticType": "Amount", "unit": "USD"}}

See :doc:`mapping` for the full table, :doc:`agents` to give an agent query and chart
tools, and :doc:`chat-ui` to draw those charts in a chat.

.. toctree::
   :hidden:

   agents
   chat-ui
   TypeScript API <typescript>
   mapping
   grain
   API Reference <autoapi/index>
   Release notes <changelog>
