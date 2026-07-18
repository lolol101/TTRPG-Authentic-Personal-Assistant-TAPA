from __future__ import annotations

from typing import Callable

from langchain_core.messages import ToolMessage

from agents_core.state import State


def create_agent_entry_node(agent_name: str) -> Callable[[State], dict]:
    """Return a node function that enters *agent_name* in the agent stack."""

    def entry_node(state: State) -> dict:
        return {
            "messages": [
                ToolMessage(
                    content=(
                        f"The agent is now the {agent_name}. "
                        "Reflect on the above conversation and begin your task."
                    ),
                    tool_call_id=state["messages"][-1].tool_calls[0]["id"],
                )
            ],
            "agents_stack": agent_name,
        }

    return entry_node


def leave_agent(state: State) -> dict:
    """Pop the agent stack and return to the senior agent."""
    messages = []
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        messages = [
            ToolMessage(
                content="Resuming dialog with the host assistant.",
                tool_call_id=last.tool_calls[0]["id"],
            )
        ]
    return {"agents_stack": "pop", "messages": messages}
