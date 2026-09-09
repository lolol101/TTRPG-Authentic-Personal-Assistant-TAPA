from __future__ import annotations

from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_core.vectorstores import VectorStore

from agents_core.state import State


def make_search_tool(vector_db: VectorStore):
    """Create a retrieval tool bound to a specific vector store instance."""

    @tool
    def search_relevant_book_data(query: str, book_name: str) -> str:
        """Search the knowledge base for chunks relevant to the query, filtered by book_name."""
        retriever = vector_db.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 5, "filter": {"book_name": book_name}},
        )
        docs = retriever.invoke(query)
        return str([d.page_content for d in docs])

    return search_relevant_book_data


@tool
def CompleteOrEscalate(completed: bool, reason: str) -> str:
    """Signal that the sub-agent task is finished and control should return to the primary agent."""
    return reason


class RAGAgent:
    def __init__(
        self,
        prompt: ChatPromptTemplate,
        llm: BaseChatModel,
        vector_db: VectorStore,
    ):
        self.prompt = prompt
        search_tool = make_search_tool(vector_db)
        self.tools = [search_tool, CompleteOrEscalate]
        self.llm = llm.bind_tools(self.tools)

    def __call__(self, state: State):
        chain = self.prompt | self.llm
        result = chain.invoke(state)
        return {"messages": [result]}


def route_rag_agent(state: State) -> Literal["rag_tools", "leave_agent"]:
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        tool_name = last_message.tool_calls[0]["name"]
        if tool_name == CompleteOrEscalate.name:
            return "leave_agent"
        return "rag_tools"
    return "leave_agent"
