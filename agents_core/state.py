from __future__ import annotations

from typing import Annotated

from langgraph.graph import MessagesState


def update_agents_stack(left: list[str], right: str | None) -> list[str]:
    """Push or pop the agent stack."""
    if right is None:
        return left
    if right == "pop":
        return left[:-1]
    return left + [right]


class State(MessagesState):
    book_name: str | None
    agents_stack: Annotated[list[str], update_agents_stack]
