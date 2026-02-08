from typing import Optional, Annotated
from langgraph.graph import MessagesState

def update_agents_stack(left: list[str], right: Optional[str]) -> list[str]:
    """Push or pop the state of current agent."""
    if right is None:
        return left
    if right == "pop":
        return left[:-1]
    return left + [right]

class State(MessagesState):
    book_name: Optional[str]
    agents_stack: Annotated[list[str], update_agents_stack]
    