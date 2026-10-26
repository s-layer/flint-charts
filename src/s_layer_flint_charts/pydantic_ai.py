"""
A Pydantic AI toolset that lets an agent query semantic views and chart the results.

Needs the ``pydantic-ai`` extra. One ``query_<view>`` tool per semantic view runs a query and
answers with a summary and a ``result_id``; ``show_chart`` draws a result and answers with a
Flint input for the app's chart component, its ``data.url`` pointing at the rows. Rows never
pass through the model.

Example:
    .. code-block:: python

        from pydantic_ai import Agent
        from s_layer_flint_charts import ChartStore
        from s_layer_flint_charts.pydantic_ai import chart_toolset

        store = ChartStore()
        agent = Agent(
            "anthropic:claude-sonnet-4-6",
            deps_type=Conversation,
            toolsets=[chart_toolset([Sales], store=store, session_id=lambda ctx: ctx.deps.id)],
        )
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, TypeVar

from semolina import SemolinaSpecError
from semolina.spec import query_spec_schema

from s_layer_flint_charts._charts import CHART_TYPES, show_chart
from s_layer_flint_charts._query import run_query
from s_layer_flint_charts._rows import DEFAULT_ROW_CAP

try:
    from pydantic_ai import FunctionToolset, ModelRetry, RunContext, Tool
except ImportError as error:  # pragma: no cover - depends on the install
    raise ImportError(
        "chart_toolset needs the pydantic-ai extra: pip install 's-layer-flint-charts[pydantic-ai]'"
    ) from error

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from semolina import SemanticView

    from s_layer_flint_charts._charts import ChartValidator
    from s_layer_flint_charts._query import Fetch
    from s_layer_flint_charts._store import ChartStore

__all__ = ["chart_toolset"]

DepsT = TypeVar("DepsT")

_SHOW_CHART_DESCRIPTION = """\
Draw a query result as a chart the user sees. Pass the result_id a query tool returned, a chart
type, and the result column to put on each channel (x, y, color, size, theta, column, row,
tooltip). Every dimension column of the result must be on a channel, or the chart would merge
rows; the tool says so if not. The title says what the chart shows, in words. Answers with the
chart as drawn (its rows stay on the server), or with the problems to fix."""


def chart_toolset(
    views: Sequence[type[SemanticView]],
    *,
    store: ChartStore,
    session_id: Callable[[RunContext[DepsT]], str],
    validator: ChartValidator | None = None,
    theme: str | Mapping[str, object] | None = None,
    cap: int = DEFAULT_ROW_CAP,
    fetch: Fetch | None = None,
    url_prefix: str = "/flint",
) -> FunctionToolset[DepsT]:
    """
    The query and chart tools for an agent.

    Args:
        views: The semantic views the agent may query, one ``query_<view>`` tool each.
        store: Where results and charts are kept for the app's routes.
        session_id: The conversation a run belongs to, from its context (usually its deps).
        validator: Checks each chart with Flint itself, such as a started
            :class:`~s_layer_flint_charts.FlintSidecar`.
        theme: The Flint theme preset or ``ThemeSpec`` every chart gets.
        cap: The most rows a chart may draw.
        fetch: Runs a query. By default each query runs on its view's async engine.
        url_prefix: Where the app mounts :func:`~s_layer_flint_charts.server.chart_routes`.

    Returns:
        The toolset, to pass in an agent's ``toolsets``.
    """
    toolset: FunctionToolset[DepsT] = FunctionToolset()
    for view in views:
        toolset.add_tool(
            _query_tool(view, store=store, session_id=session_id, cap=cap, fetch=fetch)
        )

    async def chart(
        ctx: RunContext[DepsT],
        result_id: str,
        chart_type: str,
        encodings: dict[str, str],
        title: str,
        subtitle: str | None = None,
        chart_properties: dict[str, object] | None = None,
    ) -> dict[str, object]:
        receipt = await show_chart(
            store.session(session_id(ctx)),
            result_id=result_id,
            chart_type=chart_type,
            encodings=encodings,
            title=title,
            subtitle=subtitle,
            chart_properties=chart_properties,
            theme=theme,
            validator=validator,
            url_prefix=url_prefix,
        )
        if not receipt.ok:
            raise ModelRetry("The chart was not drawn:\n- " + "\n- ".join(receipt.problems))
        return receipt.to_dict()

    toolset.add_tool(
        Tool.from_schema(
            chart,
            name="show_chart",
            description=_SHOW_CHART_DESCRIPTION,
            json_schema=_SHOW_CHART_SCHEMA,
            takes_ctx=True,
        )
    )
    return toolset


def _query_tool(
    view: type[SemanticView],
    *,
    store: ChartStore,
    session_id: Callable[[RunContext[DepsT]], str],
    cap: int,
    fetch: Fetch | None,
) -> Tool[DepsT]:
    async def query(ctx: RunContext[DepsT], **spec: Any) -> dict[str, object]:
        try:
            return await run_query(store.session(session_id(ctx)), view, spec, cap=cap, fetch=fetch)
        except SemolinaSpecError as error:
            raise ModelRetry(str(error)) from error

    about = (view.__doc__ or "").strip()
    description = (
        f"Query the {view._view_name} semantic view. "
        + (f"{about} " if about else "")
        + "Answers with a summary of the result (its columns, their ranges and a few rows) and "
        "a result_id to pass to show_chart. Ask for the grain the chart needs."
    )
    return Tool.from_schema(
        query,
        name=_tool_name(view._view_name),
        description=description,
        json_schema=query_spec_schema(view),
        takes_ctx=True,
    )


def _tool_name(view_name: str) -> str:
    return "query_" + re.sub(r"\W+", "_", view_name.rsplit(".", 1)[-1]).strip("_").lower()


_SHOW_CHART_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "result_id": {"type": "string", "description": "The result to draw, from a query tool."},
        "chart_type": {"type": "string", "enum": sorted(CHART_TYPES)},
        "encodings": {
            "type": "object",
            "description": 'A result column per channel, such as {"x": "month", "y": "revenue"}.',
            "additionalProperties": {"type": "string"},
        },
        "title": {"type": "string", "description": "What the chart shows, in words."},
        "subtitle": {"type": "string"},
        "chart_properties": {
            "type": "object",
            "description": 'Flint chart properties, such as {"stackMode": "layered"}.',
        },
    },
    "required": ["result_id", "chart_type", "encodings", "title"],
    "additionalProperties": False,
}
