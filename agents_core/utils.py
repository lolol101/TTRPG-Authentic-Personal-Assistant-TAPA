from typing import Callable
from langchain_core.tools import tool
from langchain_core.messages import ToolMessage

import sys
import os

sys.path.append(os.path.abspath(".."))
from agents_core.state import State

def create_agent_entry_node(agent_name: str) -> Callable:
    def entry_agent_node(state: State):
        """Enters inside the {agent_name} agent and continues agent's flow with him"""
        return {
            "messages": [
                ToolMessage(
                    content=f"""
                    The agent is now the {agent_name}. Reflect on the above conversation and begin your task.
                    Do not provide any additional information and complete the task as you were designed to make it. 
                    """,
                    tool_call_id=state["messages"][-1].tool_calls[0]["id"]
                )
            ],
            "agents_stack": agent_name,
        }
    
    return entry_agent_node

def leave_agent(state: State):
    """Pop the agents stack and return to the senior agent."""
    messages = []
    if state["messages"][-1].tool_calls:
        messages= [
            ToolMessage(
                content="Resuming dialog with the host assistant. Please reflect on the past conversation and assist the user as needed.",
                tool_call_id=state["messages"][-1].tool_calls[0]["id"]
            )
        ]
    return {
        "agents_stack": "pop",
        "messages": messages,
    }