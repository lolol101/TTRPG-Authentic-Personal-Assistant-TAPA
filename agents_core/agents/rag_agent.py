import os
import sys
from typing import Optional

from langchain_community.vectorstores import Chroma
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field
from langchain_core.tools import tool

sys.path.append(os.path.abspath(".."))
from agents_core.state import State
from agents_core.agents.base_agent import BaseAgent

class RAGAgent(BaseAgent):
    def __init__(self, prompt: str, llm: BaseChatModel, vector_db: Chroma):
        self.vector_db = vector_db
        self.tools = [
            make_search_relevant_book_data_tool(self.vector_db),
            CompleteOrEscalate
        ]
        
        super().__init__(
            prompt | llm
                .bind_tools(self.tools)
                .with_retry(retry_if_exception_type=(Exception,), stop_after_attempt=2)
        )

def route_rag_agent(state: State):
    """Routes the rag agent to the appropriate tool based on the current task."""
    tool_calls = state["messages"][-1].tool_calls
    did_cancel = any(tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls)
    if did_cancel: 
        return "leave_agent"
    return "rag_tools"

#========================Tools========================

def make_search_relevant_book_data_tool(vector_db):
    @tool
    def search_relevant_book_data(
        query: str, book_name: Optional[str] = None
    ) -> list[str]:
        
        """
        Search for relevant data chunks for given query and book.

        Args:
            query (str): The query that will be used to search relevant information.
            book_name (Optional[str]): The name of the source book. Defaults to None.

        Returns:
            list[str]: A list of relevant data chunks based on the query and book.
        """
        retriever = vector_db.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 10, "filter": {"book_name": book_name}},
        )
        relevant_data = [x.page_content for x in retriever.invoke(query)]
        return relevant_data
    return search_relevant_book_data

class CompleteOrEscalate(BaseModel):
    """A tool to mark the current task as completed and/or to escalate control of the dialog to the senior assistant"""
    completed: bool = Field(description="Mark that shows whether the current task is completed or not.")
    reason: str = Field(description="A short explanation why 'completed' mark is true or false.")

    class Config:
        json_schema_extra = {
            "example": {
                "cancel": True,
                "reason": "User changed their mind about the current task.",
            },
            "example 2": {
                "cancel": True,
                "reason": "I have fully completed the task.",
            },
            "example 3": {
                "cancel": False,
                "reason": "I need to search more information to complete my task.",
            },
        }

