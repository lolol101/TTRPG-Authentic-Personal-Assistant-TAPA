from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_core.vectorstores import VectorStore
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from agents_core import prompts
from agents_core.agents.primary_agent import PrimaryAgent, route_primary_agent
from agents_core.agents.rag_agent import RAGAgent, route_rag_agent
from agents_core.state import State
from agents_core.utils import create_agent_entry_node, leave_agent


def build_graph(
    llm: BaseChatModel,
    vector_db: VectorStore,
    book_name: str,
) -> CompiledStateGraph:
    primary_agent = PrimaryAgent(
        prompts.primary_agent_prompt.partial(book_name=book_name),
        llm,
    )
    rag_agent = RAGAgent(
        prompts.rag_agent_prompt.partial(book_name=book_name),
        llm,
        vector_db,
    )

    graph_builder = StateGraph(State)

    # -- nodes --
    graph_builder.add_node("primary_agent", primary_agent)
    graph_builder.add_node("rag_agent", rag_agent)
    graph_builder.add_node("leave_agent", leave_agent)
    graph_builder.add_node("enter_rag_agent", create_agent_entry_node("rag_agent"))
    graph_builder.add_node("rag_tools", ToolNode(rag_agent.tools))

    # -- static edges --
    graph_builder.add_edge("leave_agent", "primary_agent")
    graph_builder.add_edge("enter_rag_agent", "rag_agent")
    graph_builder.add_edge("rag_tools", "rag_agent")

    # -- conditional edges --
    graph_builder.add_conditional_edges(
        "primary_agent",
        route_primary_agent,
        {
            "enter_rag_agent": "enter_rag_agent",
            END: END,
        },
    )
    graph_builder.add_conditional_edges(
        "rag_agent",
        route_rag_agent,
        {"rag_tools": "rag_tools", "leave_agent": "leave_agent"},
    )

    graph_builder.set_entry_point("primary_agent")

    return graph_builder.compile()
