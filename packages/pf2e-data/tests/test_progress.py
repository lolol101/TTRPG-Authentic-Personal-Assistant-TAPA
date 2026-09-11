import io

from app.progress import Progress, bar, format_duration


class _Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


def test_bar_fills_in_proportion() -> None:
    assert bar(0, 10, width=10) == "░" * 10
    assert bar(5, 10, width=10) == "█" * 5 + "░" * 5
    assert bar(10, 10, width=10) == "█" * 10


def test_bar_survives_an_empty_total() -> None:
    """A section can legitimately match nothing in the sitemap."""
    assert bar(0, 0, width=6) == "░" * 6


def test_bar_does_not_overflow_past_the_total() -> None:
    assert bar(15, 10, width=10) == "█" * 10


def test_duration_reads_as_time_not_seconds() -> None:
    assert format_duration(45) == "45с"
    assert format_duration(125) == "2м 05с"
    assert format_duration(3 * 3600 + 27 * 60) == "3ч 27м"


def test_a_terminal_redraws_one_line_in_place() -> None:
    stream = _Terminal()
    progress = Progress("feats", 100, stream=stream)

    progress.advance()
    progress.advance()

    assert stream.getvalue().count("\r") == 2
    assert "\n" not in stream.getvalue()


def test_a_log_file_gets_whole_lines_not_carriage_returns() -> None:
    """Redrawing into a log would pile up into an unreadable smear."""
    stream = io.StringIO()
    progress = Progress("feats", 500, stream=stream)

    for _ in range(25):
        progress.advance()

    written = stream.getvalue()
    assert "\r" not in written
    assert written.count("\n") == 1


def test_a_log_file_stays_quiet_between_milestones() -> None:
    stream = io.StringIO()
    progress = Progress("feats", 500, stream=stream)

    for _ in range(24):
        progress.advance()

    assert stream.getvalue() == ""


def test_a_slow_crawl_still_reports_before_the_next_milestone() -> None:
    """Throttled to 15s a page, 25 pages would mean six minutes of silence."""
    stream = io.StringIO()
    progress = Progress("feats", 500, stream=stream)
    progress._last_logged -= 120  # pretend two minutes have passed

    progress.advance()

    assert "осталось" in stream.getvalue() or "1/500" in stream.getvalue()


def test_finish_always_writes_the_final_state() -> None:
    stream = io.StringIO()
    progress = Progress("deities", 3, stream=stream)
    progress.advance()

    progress.finish()

    assert "1/3" in stream.getvalue()


def test_counts_toward_the_whole_run_not_just_this_section() -> None:
    stream = _Terminal()
    progress = Progress("feats", 100, stream=stream, overall_done=8000, overall_total=15000)

    progress.advance()

    assert "8001/15000" in progress.render()


def test_estimate_covers_what_is_left_of_the_run() -> None:
    stream = _Terminal()
    progress = Progress("feats", 10, stream=stream, overall_total=100, started_at=0.0)

    progress.advance()

    # Time since start is large and real here, so only assert the shape:
    # an estimate appears once at least one page has been measured.
    assert "осталось" in progress.render()
