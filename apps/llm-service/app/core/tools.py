"""The one tool the assistant may call, and how its arguments are read.

The model never writes to a sheet. It proposes changes; web-backend decides
which paths are writable and the player confirms them. Keeping the tool to
"propose" rather than "apply" is the whole safety story.
"""

import json
from typing import Any

PROPOSE_SHEET_CHANGE = "propose_sheet_change"

SHEET_CHANGE_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": PROPOSE_SHEET_CHANGE,
        "description": (
            "Предложить изменения в листе персонажа. Ничего не применяется сразу — "
            "игрок подтверждает каждое изменение вручную. Вызывай только если "
            "пользователь явно просит изменить лист (получил урон, наложено "
            "состояние, потрачен пункт героизма, повышено умение)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "changes": {
                    "type": "array",
                    "description": "Список предлагаемых изменений.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": (
                                    "Что менять. Доступно: hp_current, hp_max, level, ac, "
                                    "speed, str_mod, dex_mod, con_mod, int_mod, wis_mod, "
                                    "cha_mod, sheet_data.hero_points, sheet_data.dying, "
                                    "sheet_data.wounded, sheet_data.conditions.<состояние>, "
                                    "sheet_data.stats.<характеристика>.rank|item|temporary"
                                ),
                            },
                            "value": {
                                "description": (
                                    "Новое значение целиком, а не разница. Для умения — "
                                    "untrained, trained, expert, master или legendary."
                                ),
                            },
                            "reason": {
                                "type": "string",
                                "description": "Коротко: почему это изменение.",
                            },
                        },
                        "required": ["path", "value"],
                    },
                }
            },
            "required": ["changes"],
        },
    },
}


def parse_change_arguments(raw_arguments: str) -> list[dict[str, Any]]:
    """Reads a tool call's arguments, tolerating the shapes models produce.

    A malformed call must not fail the whole answer: the text reply is still
    useful, so anything unparseable yields no proposals rather than an error.
    """
    try:
        parsed = json.loads(raw_arguments)
    except (json.JSONDecodeError, TypeError):
        return []

    if isinstance(parsed, list):
        changes = parsed
    elif isinstance(parsed, dict):
        changes = parsed.get("changes", [])
        # Some models answer with a single change instead of a list.
        if isinstance(changes, dict):
            changes = [changes]
        elif not isinstance(changes, list):
            return []
    else:
        return []

    return [
        {
            "path": str(change["path"]),
            "value": change.get("value"),
            "reason": str(change.get("reason") or ""),
        }
        for change in changes
        if isinstance(change, dict) and change.get("path")
    ]
