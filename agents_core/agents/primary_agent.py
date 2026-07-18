from __future__ import annotations

from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langgraph.graph import END

from agents_core.state import State


@tool
def MoveToRagAgent(query: str) -> str:
    """Delegate a question to the RAG agent for retrieval-augmented research in the reference book."""
    return query


class PrimaryAgent:
    def __init__(self, prompt: ChatPromptTemplate, llm: BaseChatModel):
        self.prompt = prompt
        self.tools = [MoveToRagAgent]
        self.llm = llm.bind_tools(self.tools)

    def __call__(self, state: State) -> dict:
        chain = self.prompt | self.llm
        result = chain.invoke(state)
        return {"messages": [result]}


_TOOL_TO_NODE = {
    MoveToRagAgent.name: "enter_rag_agent",
}


def route_primary_agent(
    state: State,
) -> Literal["enter_rag_agent", "__end__"]:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        node = _TOOL_TO_NODE.get(last.tool_calls[0]["name"])
        if node:
            return node
    return END
