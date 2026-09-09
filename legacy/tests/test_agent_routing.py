"""Unit tests for agent routing functions.

These tests check the pure routing logic without requiring an LLM or vector store.
"""

from unittest.mock import MagicMock

from langgraph.graph import END

from agents_core.agents.primary_agent import (
    MoveToRagAgent,
    route_primary_agent,
)
from agents_core.agents.rag_agent import CompleteOrEscalate, route_rag_agent


def _make_state(tool_calls=None):
    msg = MagicMock()
    msg.tool_calls = tool_calls or []
    return {"messages": [msg]}


class TestRoutePrimaryAgent:
    def test_routes_to_rag(self):
        state = _make_state([{"name": MoveToRagAgent.name}])
        assert route_primary_agent(state) == "enter_rag_agent"

    def test_routes_to_end_when_no_tools(self):
        state = _make_state([])
        assert route_primary_agent(state) == END

    def test_routes_to_end_for_unknown_tool(self):
        state = _make_state([{"name": "UnknownTool"}])
        assert route_primary_agent(state) == END


class TestRouteRagAgent:
    def test_routes_to_leave_on_complete(self):
        state = _make_state([{"name": CompleteOrEscalate.name}])
        assert route_rag_agent(state) == "leave_agent"

    def test_routes_to_tools_for_other(self):
        state = _make_state([{"name": "search_relevant_book_data"}])
        assert route_rag_agent(state) == "rag_tools"

    def test_routes_to_leave_when_no_tools(self):
        state = _make_state([])
        assert route_rag_agent(state) == "leave_agent"
