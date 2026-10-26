"""The Pydantic AI toolset: an agent queries a view and charts the result."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest
from pydantic_ai import Agent, ModelMessage, ModelResponse, RunContext, TextPart, ToolCallPart
from pydantic_ai.messages import ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from s_layer_flint_charts import ChartStore
from s_layer_flint_charts.pydantic_ai import chart_toolset
from tests._arrow import table
from tests._views import Sales, monthly

if TYPE_CHECKING:
    from pydantic_ai.toolsets import FunctionToolset

pytestmark = pytest.mark.anyio


@dataclass
class Conversation:
    id: str


async def fetch(query: Any) -> Any:
    return monthly(query)


def conversation_id(ctx: RunContext[Conversation]) -> str:
    return ctx.deps.id


def toolset(store: ChartStore) -> FunctionToolset[Conversation]:
    return chart_toolset(
        [Sales], store=store, session_id=conversation_id, fetch=fetch, theme="dark"
    )


def scripted(*calls: dict[str, Any]) -> tuple[FunctionModel, list[list[Any]]]:
    """A model that makes each tool call in turn (args may name the last result_id) and stops."""
    seen: list[list[Any]] = []

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        parts = [part for message in messages for part in getattr(message, "parts", [])]
        returns: list[Any] = [p for p in parts if isinstance(p, ToolReturnPart)]
        step = sum(isinstance(p, ToolCallPart) for m in messages for p in getattr(m, "parts", []))
        seen.append(returns)
        if step == len(calls):
            return ModelResponse(parts=[TextPart("done")])
        call = dict(calls[step])
        args = dict(call["args"])
        if args.get("result_id") == "<last>":
            last: Any = returns[-1].content
            args["result_id"] = last["result_id"]
        return ModelResponse(parts=[ToolCallPart(call["tool"], args)])

    return FunctionModel(respond), seen


def tool_names(store: ChartStore) -> list[str]:
    names: list[str] = []

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        names.extend(tool.name for tool in info.function_tools)
        return ModelResponse(parts=[TextPart("done")])

    Agent(FunctionModel(respond), deps_type=Conversation, toolsets=[toolset(store)]).run_sync(
        "hi", deps=Conversation("a")
    )
    return names


def test_one_query_tool_per_view_and_show_chart() -> None:
    assert sorted(tool_names(ChartStore())) == ["query_sales", "show_chart"]


async def test_query_then_chart() -> None:
    store = ChartStore()
    model, seen = scripted(
        {
            "tool": "query_sales",
            "args": {"metrics": ["revenue"], "dimensions": ["ordered_at__month", "region"]},
        },
        {
            "tool": "show_chart",
            "args": {
                "result_id": "<last>",
                "chart_type": "Line Chart",
                "encodings": {"x": "ordered_at__month", "y": "revenue", "color": "region"},
                "title": "Revenue by month",
            },
        },
    )
    agent = Agent(model, deps_type=Conversation, toolsets=[toolset(store)])
    result = await agent.run("chart revenue", deps=Conversation("a"))
    assert result.output == "done"
    summary = seen[1][-1].content
    assert summary["rows"] == 6
    receipt = seen[2][-1].content
    assert receipt["ok"]
    chart_id = receipt["chart_id"]
    assert receipt["chart"]["data"] == {"url": f"/flint/charts/{chart_id}/rows"}
    assert receipt["chart"]["theme_spec"] == "dark"
    session = store.get("a")
    assert session is not None
    assert session.chart(chart_id) is not None
    assert store.get("b") is None


async def test_a_bad_spec_is_sent_back_to_the_model() -> None:
    model, seen = scripted({"tool": "query_sales", "args": {"metrics": ["profit"]}})
    agent = Agent(model, deps_type=Conversation, toolsets=[toolset(ChartStore())])
    await agent.run("q", deps=Conversation("a"))
    retry = seen[1][-1]
    assert retry.outcome == "retried"
    assert "Sales has no field 'profit'" in str(retry.content)


async def test_a_chart_that_merges_rows_is_sent_back_to_the_model() -> None:
    model, seen = scripted(
        {
            "tool": "query_sales",
            "args": {"metrics": ["revenue"], "dimensions": ["ordered_at__month", "region"]},
        },
        {
            "tool": "show_chart",
            "args": {
                "result_id": "<last>",
                "chart_type": "Line Chart",
                "encodings": {"x": "ordered_at__month", "y": "revenue"},
                "title": "Revenue",
            },
        },
    )
    agent = Agent(model, deps_type=Conversation, toolsets=[toolset(ChartStore())])
    await agent.run("q", deps=Conversation("a"))
    retry = seen[2][-1]
    assert retry.outcome == "retried"
    assert "The chart was not drawn" in str(retry.content)
    assert "region" in str(retry.content)


async def binary_regions(query: Any) -> Any:
    return table({"REGION": [b"EU", b"US"], "REVENUE": [1.0, 2.0]})


async def test_a_column_that_cannot_be_charted_is_sent_back_to_the_model() -> None:
    model, seen = scripted(
        {"tool": "query_sales", "args": {"metrics": ["revenue"], "dimensions": ["region"]}}
    )
    tools = chart_toolset(
        [Sales], store=ChartStore(), session_id=conversation_id, fetch=binary_regions
    )
    agent = Agent(model, deps_type=Conversation, toolsets=[tools])
    await agent.run("q", deps=Conversation("a"))
    retry = seen[1][-1]
    assert retry.outcome == "retried"
    assert "region" in str(retry.content)
