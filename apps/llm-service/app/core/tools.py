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
                                    "Что менять. Числа: hp_current, hp_max, level, ac, "
                                    "speed, str_mod, dex_mod, con_mod, int_mod, wis_mod, "
                                    "cha_mod, sheet_data.ability_scores.<str|dex|con|int|"
                                    "wis|cha> (значение характеристики — заполняй его вместе "
                                    "с соответствующим *_mod, значение = 10 + 2×модификатор), "
                                    "sheet_data.hero_points, sheet_data.dying, "
                                    "sheet_data.wounded, sheet_data.conditions.<состояние>, "
                                    "sheet_data.stats.<характеристика>.rank|item|temporary. "
                                    "Текст: name, ancestry, background, class_name, "
                                    "sheet_data.heritage|deity|languages|size|alignment|"
                                    "traits|senses|resistances|notes|player_name, "
                                    "sheet_data.bio.<ethnicity|nationality|birthplace|age|"
                                    "gender|height|weight|appearance>, "
                                    "sheet_data.personality.<attitude|beliefs|likes|dislikes|"
                                    "catchphrases>, "
                                    "sheet_data.campaign.<notes|allies|enemies|organizations>. "
                                    "Других полей в этих группах нет — свободный рассказ о "
                                    "персонаже клади в sheet_data.notes. "
                                    "Карточки (список объектов): sheet_data.inventory.worn|"
                                    "ready|other, sheet_data.ancestry_feats|skill_feats|"
                                    "general_feats|class_feats|bonus_feats, sheet_data.spells|"
                                    "focus_spells|innate_spells"
                                ),
                            },
                            "value": {
                                "description": (
                                    "Новое значение целиком, а не разница. Для умения — "
                                    "untrained, trained, expert, master или legendary. "
                                    "Для карточек — весь список целиком, каким он должен "
                                    "стать. Карточка это плоский объект; заполняй в ней "
                                    "все поля, которые найденная страница правил "
                                    "действительно называет, а не только name. "
                                    "Черта: name, level, slot (класса/происхождения/"
                                    "навыков/общая), actions, rarity, traits, "
                                    "prerequisites, frequency, trigger, requirements, "
                                    "description, special. "
                                    "Предмет: name, level, price, bulk, quantity, usage, "
                                    "hands, rarity, traits, invested, activate, frequency, "
                                    "trigger, requirements, description. "
                                    "Заклинание: name, level (круг), actions (сотворение), "
                                    "prepared, rarity, traditions, traits, components, "
                                    "range, area, targets, save, duration, description, "
                                    "heightened. "
                                    "Поле, о котором страница молчит, оставляй пустым — "
                                    "не придумывай ни предварительные условия, ни цену, "
                                    "ни стоимость в действиях. Если знаешь книгу-источник, "
                                    "укажи её в поле source; если пишешь по памяти — не "
                                    "указывай, карточка будет помечена автоматически."
                                ),
                            },
                            "reason": {
                                "type": "string",
                                "description": "Коротко: почему это изменение.",
                            },
                            "basis": {
                                "description": (
                                    "Текущее значение этого поля в листе, как ты его "
                                    "прочитал. Обязательно для числовых полей: по нему "
                                    "проверяется, что расчёт шёл от реального состояния."
                                ),
                            },
                            "delta": {
                                "description": (
                                    "На сколько меняется значение: -12 при уроне 12, "
                                    "+1 при повышении. Должно выполняться "
                                    "basis + delta = value."
                                ),
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
            # The workings, when the model supplied them. web-backend checks
            # them against the sheet; absent, the change is simply unverified.
            "basis": change.get("basis"),
            "delta": change.get("delta"),
        }
        for change in changes
        if isinstance(change, dict) and change.get("path")
    ]


ASK_CLARIFICATION = "ask_clarifying_question"

CLARIFY_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": ASK_CLARIFICATION,
        "description": (
            "Спросить игрока, что именно он имеет в виду, ВМЕСТО того чтобы "
            "предлагать правку листа. Вызывай только когда без ответа правка "
            "может оказаться неверной: непонятно, какое поле менять, от какого "
            "значения считать или сколько именно. Если всё ясно — не спрашивай, "
            "а сразу вызывай propose_sheet_change."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Один короткий вопрос по существу.",
                },
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Готовые варианты ответа, если они очевидны — игрок "
                        "выберет в один клик. Не обязательно."
                    ),
                },
            },
            "required": ["question"],
        },
    },
}


def parse_clarification(raw_arguments: str) -> dict[str, Any] | None:
    """Reads a clarification call, or returns None if it says nothing useful."""
    try:
        parsed = json.loads(raw_arguments)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None

    question = str(parsed.get("question") or "").strip()
    if not question:
        return None

    raw_options = parsed.get("options")
    options = [str(option) for option in raw_options] if isinstance(raw_options, list) else []
    return {"question": question, "options": options[:5]}


REWRITE_SEARCH_QUERY = "search_the_rulebooks_in_english"

SEARCH_QUERY_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": REWRITE_SEARCH_QUERY,
        "description": (
            "Дать английский поисковый запрос по книге правил для вопроса "
            "игрока. Книги правил на английском, поэтому русский вопрос "
            "находит нужную страницу заметно хуже. Вызывай, если вопрос не "
            "на английском или сформулирован разговорно. Если вопрос уже "
            "короткий и английский — не вызывай инструмент вовсе."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Короткий запрос из терминов правил: название "
                        "действия, черты, заклинания, снаряжения, состояния. "
                        "Не переводи дословно и не пиши предложение — пиши "
                        "то, как это называется в книге. Пример: вопрос "
                        "«Что делает действие Устрашение?» → "
                        "«Demoralize action»."
                    ),
                }
            },
            "required": ["query"],
        },
    },
}


def parse_search_query(raw_arguments: str) -> str | None:
    """Reads a rewrite call, or returns None if it says nothing usable."""
    try:
        parsed = json.loads(raw_arguments)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None

    query = str(parsed.get("query") or "").strip()
    # A "rewrite" that came back as a whole paragraph is the model answering
    # the question instead of naming it; embedding that buys nothing.
    return query if query and len(query) <= 200 else None


PLAN_SHEET_WORK = "plan_sheet_work"

SHEET_PLAN_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": PLAN_SHEET_WORK,
        "description": (
            "Разбить просьбу изменить лист персонажа на разделы листа, которых "
            "она касается, чтобы по каждому отдельно найти правила. Вызывай "
            "ТОЛЬКО если игрок просит менять лист (собрать персонажа, добавить "
            "снаряжение, выбрать черты, заполнить биографию). На обычный вопрос "
            "по правилам инструмент не вызывай вовсе."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "areas": {
                    "type": "array",
                    "description": "Затронутые разделы, по одному на каждый.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "area": {
                                "type": "string",
                                "enum": [
                                    "ancestry",
                                    "background",
                                    "class",
                                    "skills",
                                    "feats",
                                    "equipment",
                                    "spells",
                                    "bio",
                                ],
                                "description": "Раздел листа.",
                            },
                            "query": {
                                "type": "string",
                                "description": (
                                    "Короткий поисковый запрос по правилам для "
                                    "этого раздела. Лучше по-английски — книги "
                                    "правил на английском."
                                ),
                            },
                        },
                        "required": ["area", "query"],
                    },
                }
            },
            "required": ["areas"],
        },
    },
}
