from __future__ import annotations

import json
from typing import Annotated, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langchain_core.vectorstores import VectorStore
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from agents_core.agents.rag_agent import CompleteOrEscalate, make_search_tool
from agents_core.state import State


@tool
def update_sheet(
    patch_json: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState],
) -> Command:
    """Apply field-level updates to the character sheet.

    *patch_json* must be a JSON object mapping PDF field names to new string
    values. Only the specified fields are overwritten.
    """
    try:
        patch = json.loads(patch_json)
    except json.JSONDecodeError as exc:
        msg = f"Invalid JSON: {exc}"
        return Command(update={"messages": [ToolMessage(msg, tool_call_id=tool_call_id)]})

    if not isinstance(patch, dict):
        msg = "Patch must be a JSON object, not a list or scalar."
        return Command(update={"messages": [ToolMessage(msg, tool_call_id=tool_call_id)]})

    current: dict = dict(state.get("sheet_data") or {})
    current.update({k: str(v) for k, v in patch.items()})

    changed = ", ".join(patch.keys())
    confirmation = f"Sheet updated — modified: {changed}."
    return Command(
        update={
            "sheet_data": current,
            "messages": [ToolMessage(confirmation, tool_call_id=tool_call_id)],
        },
    )


class SheetAgent:
    def __init__(
        self,
        prompt: ChatPromptTemplate,
        llm: BaseChatModel,
        vector_db: VectorStore,
    ):
        self.prompt = prompt
        search_tool = make_search_tool(vector_db)
        self.tools = [search_tool, update_sheet, CompleteOrEscalate]
        self.llm = llm.bind_tools(self.tools)

    def __call__(self, state: State) -> dict:
        from services.sheet_parser import sheet_data_as_text

        sheet_text = sheet_data_as_text(state.get("sheet_data") or {})
        prompt = self.prompt.partial(sheet_data=sheet_text)
        chain = prompt | self.llm
        result = chain.invoke(state)
        return {"messages": [result]}


def route_sheet_agent(state: State) -> Literal["sheet_tools", "leave_agent"]:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        if last.tool_calls[0]["name"] == CompleteOrEscalate.name:
            return "leave_agent"
        return "sheet_tools"
    return "leave_agent"
