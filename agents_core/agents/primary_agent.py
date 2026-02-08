import os
import sys

from pydantic import BaseModel, Field

from langchain_core.language_models import BaseChatModel
from langgraph.prebuilt import tools_condition
from langgraph.graph import END

sys.path.append(os.path.abspath(".."))
from agents_core.state import State
from agents_core.agents.base_agent import BaseAgent


class PrimaryAgent(BaseAgent):
    def __init__(self, prompt: str, llm: BaseChatModel):
        self.tools = [
            MoveToRagAgent
        ]
        
        super().__init__(
            prompt | llm
                .bind_tools(self.tools)
                .with_retry(retry_if_exception_type=(Exception,), stop_after_attempt=2)
        )

def route_primary_agent(state: State):
    """Routes the primary agent to the appropriate tool based on the current task. 
    Follows ReAct ideas so routes only single tool at once."""
    route = tools_condition(state)
    if route == END:
        return END
    tool_calls = state["messages"][-1].tool_calls
    if tool_calls:
        if tool_calls[0]["name"] == MoveToRagAgent.__name__:
            return "enter_rag_agent"
    raise ValueError("Invalid route")

#========================Tools========================

class MoveToRagAgent(BaseModel):
    """Transfers work to a specialized assistant to handle flight updates and cancellations."""
    
    query: str = Field(
        description="A query to the RagAgent that represents the information needed to retrieve."
    )
    
    class Config:
        json_schema_extra = {
            "example1": {
                "query": "What are the classes in the game?"
            },
            "example2": {
                "query": "How does the Actions work?"
            }
        }

