from app.core.text_filter import MARKERS, TextFilter, strip_markup


def _stream(pieces: list[str]) -> str:
    f = TextFilter()
    return "".join(f.feed(p) for p in pieces) + f.flush()


def test_plain_text_passes_through_untouched() -> None:
    assert strip_markup("Захват обездвиживает цель.") == "Захват обездвиживает цель."


def test_a_stray_closing_tag_is_removed() -> None:
    """Observed in a real answer: the model ended its reply with this."""
    assert strip_markup("Ответ готов.</tool_call>") == "Ответ готов."


def test_both_halves_of_the_tool_call_markup_go() -> None:
    assert strip_markup("<tool_call>жми</tool_call>") == "жми"


def test_special_tokens_are_removed() -> None:
    assert strip_markup("текст<|im_end|>") == "текст"


def test_streaming_removes_a_tag_split_across_chunks() -> None:
    """Chunks arrive mid-token, so a marker rarely lands whole in one piece."""
    assert _stream(["Ответ.", "</tool", "_call>"]) == "Ответ."


def test_streaming_holds_back_only_what_might_be_a_tag() -> None:
    assert _stream(["Цена 5 < 10, а "]) == "Цена 5 < 10, а "


def test_a_lone_angle_bracket_is_not_swallowed() -> None:
    """Held back while it might start a marker, released when it cannot."""
    assert _stream(["СЛ <", " 15"]) == "СЛ < 15"


def test_text_after_a_removed_tag_still_arrives() -> None:
    assert _stream(["раз", "</tool_call>", "два"]) == "раздва"


def test_flush_releases_a_dangling_prefix_that_never_completed() -> None:
    """A reply that genuinely ends in "<" must not lose the character."""
    assert _stream(["итог <"]) == "итог <"


def test_nothing_is_held_back_forever() -> None:
    f = TextFilter()
    f.feed("<tool")
    assert f.flush() == "<tool"


def test_every_marker_is_stripped() -> None:
    for marker in MARKERS:
        assert strip_markup(f"до{marker}после") == "допосле"
