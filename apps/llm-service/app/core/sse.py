"""Server-sent events framing.

Kept separate from the endpoints so the wire format is defined once and can
be tested without a running model.
"""

import json
from typing import Any


def event(name: str, payload: Any) -> str:
    """One SSE frame.

    `ensure_ascii=False` keeps Russian readable on the wire; the newlines are
    the protocol's record separator, so a frame must end with a blank line.
    """
    body = json.dumps(payload, ensure_ascii=False)
    return f"event: {name}\ndata: {body}\n\n"
