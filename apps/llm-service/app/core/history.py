"""Fitting a conversation into the part of the window we can spare.

The rules context is retrieved fresh on every turn and is the whole reason
this service exists, so it gets the window first; the dialogue takes what is
left. When the dialogue stops fitting, whole turns are dropped from the
oldest end rather than truncated — half an answer misleads the model more
than a missing one, and the reader can at least be told where memory ends.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Russian runs roughly two to three characters per token in the BPE
#: vocabularies these models use. The low end is deliberate: overestimating
#: the cost wastes a little window, underestimating it overruns the model.
CHARS_PER_TOKEN = 2.5

#: Role tag and separators the chat format adds around every message.
MESSAGE_OVERHEAD_TOKENS = 4


@dataclass(frozen=True)
class Turn:
    role: str
    text: str


@dataclass(frozen=True)
class FittedHistory:
    """What actually fits, and how much was left behind."""

    messages: list[Turn] = field(default_factory=list)
    dropped: int = 0
    tokens: int = 0


def estimate_tokens(text: str) -> int:
    """Approximate token count without pulling in a tokenizer dependency."""
    return int(len(text) / CHARS_PER_TOKEN)


def _cost(turn: Turn) -> int:
    return estimate_tokens(turn.text) + MESSAGE_OVERHEAD_TOKENS


def fit_history(messages: list[Turn], budget: int) -> FittedHistory:
    """Keeps the newest turns that fit inside `budget`."""
    kept: list[Turn] = []
    total = 0

    for turn in reversed(messages):
        cost = _cost(turn)
        if total + cost > budget:
            break
        kept.append(turn)
        total += cost

    kept.reverse()

    # An assistant turn at the top would read as something the player said,
    # since the question it answered is no longer there.
    while kept and kept[0].role != "user":
        total -= _cost(kept[0])
        kept.pop(0)

    return FittedHistory(messages=kept, dropped=len(messages) - len(kept), tokens=total)


def retrieval_query(question: str, history: list[Turn]) -> str:
    """What to embed for a question that leans on the one before it.

    "А если он в тяжёлой броне?" matches no rule page on its own. Only the
    player's previous question is added: the assistant's prose is long enough
    to swamp the actual words in the embedding.
    """
    previous = next((turn for turn in reversed(history) if turn.role == "user"), None)
    if previous is None:
        return question
    return f"{previous.text}\n{question}"
