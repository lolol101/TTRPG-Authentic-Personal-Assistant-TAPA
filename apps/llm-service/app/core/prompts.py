from typing import Any

from app.core.history import Turn

#: Replayed live chat, 2026-10-01: given one found page (Slow), the model
#: listed Magic Missile, Color Spray and Sleep "по стандартным правилам" —
#: Color Spray is not even in Remaster — and worked out "Slow from level 3".
#: "Answer only from the context" did not stop it: it read the found page as
#: the answer's source and its own memory as fair supplement. So the rule is
#: stated per claim — every name, number and level — and the supplement is
#: named for what it is.
ASK_SYSTEM_INSTRUCTIONS = (
    "Ты — помощник по правилам Pathfinder 2e (только открытый ORC-контент из "
    "официальных паков foundryvtt/pf2e, на английском). Отвечай на русском, "
    "кратко и по делу.\n\n"
    "К вопросу приложены страницы книг правил, найденные поиском. Каждое "
    "правило, число, уровень и название (заклинания, черты, предмета, "
    "действия), которое ты называешь, должно стоять на этих страницах. Чего на "
    "них нет — не называй и не вычисляй, даже если уверен и даже с оговоркой "
    "«обычно» или «по стандартным правилам»: так твоя память выдаёт себя за "
    "книгу. Если найденного не хватает для полного ответа — ответь тем, что "
    "есть, и прямо скажи, чего в найденных правилах нет.\n\n"
    "Страницы нашёл поиск, а не прислал игрок: не пиши «как вы привели» или "
    "«в вашем запросе». Игрок не видит ни страниц, ни слова «контекст» — "
    "говори «в книгах правил» или «в найденных правилах»."
)

CHARACTER_INSTRUCTIONS = (
    "Ниже дан лист персонажа игрока. Модификаторы в нём уже посчитаны — бери "
    "их как есть и не пересчитывай. Если вопрос касается этого персонажа, "
    "опирайся на его числа. Лист персонажа не является источником правил: "
    "сами правила бери только из найденных правил при вопросе."
)


HISTORY_INSTRUCTIONS = (
    "Перед последним вопросом идут предыдущие сообщения этого чата. Они нужны "
    "только чтобы понимать, о чём спрашивает игрок: твои прошлые ответы не "
    "являются источником правил. Правила бери из найденных правил при "
    "последнем вопросе."
)


EDIT_INSTRUCTIONS = (
    "Если игрок просит изменить лист (получил урон, наложено состояние, "
    "потрачен пункт героизма, повысилось умение) — вызови инструмент "
    "propose_sheet_change. Изменения не применяются сразу: игрок подтверждает "
    "их вручную, поэтому предлагай только то, о чём тебя действительно "
    "попросили, и передавай новое значение целиком, а не разницу. "
    "Для числовых полей обязательно показывай выкладку: basis — текущее "
    "значение из листа выше, delta — на сколько меняешь, value — результат. "
    "Должно сходиться: basis + delta = value. Значение basis бери из листа, "
    "не придумывай: расчёт от несуществующего состояния будет отклонён. "
    "Если игрок просит заполнить лист целиком — собрать персонажа, добавить "
    "снаряжение, черты, биографию — делай это одним вызовом со всеми "
    "изменениями сразу, а не по одному полю за раз. Такая сборка не "
    "закончена, пока в ней остались невыбранные слоты: у каждого из 16 "
    "навыков и Восприятия должен быть явно проставлен rank (untrained — тоже "
    "осознанный выбор, а не то поле, которое можно молча пропустить); под "
    "класс и происхождение должны быть выбраны черты на каждый слот, который "
    "даёт таблица персонажа на этом уровне (черта происхождения, черты "
    "класса, черты навыков, общие черты — сколько именно, зависит от класса "
    "и уровня, смотри в найденных правилах); для каждой характеристики "
    "значение (sheet_data.ability_scores.<str|dex|con|int|wis|cha>) "
    "выставляется вместе с её модификатором (<x>_mod) — значение = "
    "10 + 2×модификатор, иначе на листе появится несовпадение. Если внутри "
    "одного из этих пунктов нет явно лучшего варианта (какую из двух "
    "равноценных общих черт взять) — выбери сам и коротко объясни выбор в "
    "reason, не оставляй слот пустым; спрашивай через "
    "ask_clarifying_question только когда неясно то, что действительно "
    "меняет результат — например, какую роль в партии играет персонаж. Для "
    "Карточка черты, предмета или заклинания — это стат-блок со страницы, а "
    "не одно название: найденная страница называет уровень, дескрипторы, "
    "стоимость в действиях, предварительные условия, цену, вес, требования — "
    "перенеси в карточку всё, что там сказано, и полное описание тоже. Чего "
    "на странице нет — оставь пустым: пустое поле игрок дозаполнит сам, а "
    "выдуманное условие или цена выглядят как правило и тем опасны. "
    "Для текстовых полей и карточек basis и delta не нужны. Игрок и так подтверждает каждое "
    "предложение в интерфейсе — не спрашивай разрешения текстом вроде "
    "«Согласовать?» вместо вызова инструмента: это лишний шаг, а не "
    "осторожность. Спрашивай текстом только через ask_clarifying_question, "
    "и только когда без ответа предложение будет неверным — например, "
    "неясно, какое из двух умений повышать."
)


#: Told to the model when retriever.is_weak found nothing close to the
#: question — a second, code-checked reason to admit the gap, independent of
#: the model noticing on its own. See settings.retrieval_weak_distance.
WEAK_RETRIEVAL_NOTICE = (
    "(Поиск не нашёл ничего похожего на точное совпадение — расстояние до "
    "ближайшего фрагмента выше порога уверенного попадания. Если ни один из "
    "них не отвечает на вопрос по существу, а не по касательной, так и "
    "скажи: ответа в правилах не нашлось. Не подгоняй смысл под то, что "
    "нашлось.)\n\n"
)


#: A bare "(контекст не найден)" was not enough: measured on "Что делает
#: состояние Sickened" with selection on, the model met an empty context and
#: wrote the condition out from memory — wrongly. An irrelevant page in the
#: context had, by accident, been what kept it honest.
NO_CONTEXT_NOTICE = (
    "(в книгах правил ничего подходящего по этому вопросу не нашлось. Не "
    "отвечай про правила по памяти — прямо скажи, что в правилах ответа не "
    "нашлось. Числа из листа персонажа, если он дан, брать можно.)"
)

#: Measured live with a single "keep what answers по существу" list: "Что
#: делает действие Толчок?" went from five pages to one, and the player lost
#: Shoving Sweep and Brutish Shove — related feats worth seeing next to the
#: answer. So the selector sorts into main and related and drops only what
#: is neither.
SELECT_INSTRUCTIONS = (
    "Ты отбираешь фрагменты книг правил Pathfinder 2e для ответа на вопрос "
    "игрока. Ниже вопрос и пронумерованные фрагменты. Вызови инструмент и "
    "разложи номера фрагментов на две группы. main — фрагменты о том самом "
    "правиле, действии, состоянии, предмете или заклинании, о котором "
    "спрашивают, и то, без чего ответ будет неполным. related — фрагменты на "
    "ту же тему, которые игроку полезно увидеть рядом с ответом: варианты и "
    "черты с этим действием, связанные состояния, похожие заклинания. "
    "Фрагменты, совпавшие только по слову или говорящие о другом, не клади "
    "никуда — они будут отброшены. Если не подходит ни один — вызови "
    "инструмент с пустыми списками. На сам вопрос не отвечай."
)

DIGEST_INSTRUCTIONS = (
    "Ты готовишь выжимку из книг правил Pathfinder 2e для ответа на вопрос "
    "игрока. Ниже вопрос и пронумерованные фрагменты. Вызови инструмент: в "
    "extract перенеси из подходящих фрагментов всё, что нужно для ответа — "
    "условия, ограничения, числа — по-английски и словами книги, без "
    "собственных выводов и без того, чего во фрагментах нет. После каждого "
    "утверждения ставь номер фрагмента в квадратных скобках. В used перечисли "
    "номера фрагментов, на которые опирается выжимка. Если не подходит ни один "
    "фрагмент — передай пустые extract и used. На сам вопрос не отвечай."
)


def _fragments(retrieved: list[dict[str, Any]], with_text: bool = True) -> str:
    return "\n\n".join(
        f"[{i + 1}] {r['metadata']['title']} "
        f"(источник: {r['metadata'].get('source_book') or 'неизвестен'})"
        + (f":\n{r['text']}" if with_text else "")
        for i, r in enumerate(retrieved)
    )


def _context_block(
    retrieved: list[dict[str, Any]], weak: bool = False, digest: str | None = None
) -> str:
    if not retrieved:
        return NO_CONTEXT_NOTICE
    notice = WEAK_RETRIEVAL_NOTICE if weak else ""
    if digest:
        return (
            f"{notice}Выжимка из найденных правил (номера в скобках — источники ниже):\n"
            f"{digest}\n\nИсточники:\n{_fragments(retrieved, with_text=False)}"
        )
    return notice + _fragments(retrieved)


def build_narrowing_messages(
    instructions: str, question: str, retrieved: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """The selection or digest call: the question and every fragment, numbered."""
    return [
        {"role": "system", "content": instructions},
        {"role": "user", "content": f"Вопрос: {question}\n\nФрагменты:\n{_fragments(retrieved)}"},
    ]


def build_system_prompt(
    character_context: str | None = None,
    allow_sheet_edits: bool = False,
    with_history: bool = False,
) -> str:
    parts = [ASK_SYSTEM_INSTRUCTIONS]
    if character_context:
        parts.append(f"{CHARACTER_INSTRUCTIONS}\n\nЛист персонажа:\n{character_context}")
        if allow_sheet_edits:
            parts.append(EDIT_INSTRUCTIONS)
    if with_history:
        parts.append(HISTORY_INSTRUCTIONS)
    return "\n\n".join(parts)


def build_ask_messages(
    question: str,
    retrieved: list[dict[str, Any]],
    character_context: str | None = None,
    allow_sheet_edits: bool = False,
    history: list[Turn] | None = None,
    retry_feedback: str | None = None,
    weak: bool = False,
    digest: str | None = None,
) -> list[dict[str, Any]]:
    """Instructions, then the remembered turns, then this question.

    The retrieved rules travel with the question rather than sitting in the
    system message: they were retrieved for *this* question, and putting them
    above the dialogue invites the model to answer an earlier one with them.

    retry_feedback replaces the question turn instead of following it: this
    is web-backend reporting what its validator did with the model's last
    proposal, not a new question, so no rules context is attached to it.
    """
    history = history or []

    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": build_system_prompt(
                character_context, allow_sheet_edits, with_history=bool(history)
            ),
        }
    ]
    messages.extend({"role": turn.role, "content": turn.text} for turn in history)

    if retry_feedback is not None:
        messages.append({"role": "user", "content": retry_feedback})
        return messages

    messages.append(
        {
            "role": "user",
            "content": (
                f"Найденные правила:\n{_context_block(retrieved, weak, digest)}\n\n"
                f"Вопрос: {question}"
            ),
        }
    )
    return messages
