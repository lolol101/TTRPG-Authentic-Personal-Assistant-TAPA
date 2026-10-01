"""Puts the context modes side by side on the same questions.

settings.context_mode has two candidates for judging retrieved rules
("select" and "digest") and the baseline ("off"). This runs each question of
the golden set — plus any extra questions given in a file, one per line —
through each mode in-process and prints, per mode: whether the golden
expectations held, the latency, how much context the answering model read,
and which pages it was given.

Not part of pytest: it needs the live index, the embedding server and a
configured LLM, and costs up to three model calls per question per mode.
Run from apps/llm-service:

    uv run python -m evals.compare_context_modes [--modes off select digest]
                                                 [--extra questions.txt]

The query rewrite is a model call too, so two modes can search slightly
differently for the same question; read the page lists before blaming the
mode for a difference.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.api.ask import _prepare
from app.core.config import settings
from app.core.llm_provider import complete
from app.schemas.ask import AskRequest
from evals.run_evals import GOLDEN_PATH, check_case


@dataclass
class Run:
    passed: bool | None
    seconds: float
    context_chars: int
    pages: list[str]
    answer: str
    failures: list[str] = field(default_factory=list)


def _run(case: dict, mode: str) -> Run:
    settings.context_mode = mode
    payload = AskRequest(question=case["question"], character_context=case.get("character_context"))

    started = time.monotonic()
    retrieved, messages, _, _ = _prepare(payload)
    answer = complete(messages).text
    seconds = time.monotonic() - started

    failures = check_case(case, answer, retrieved) if case.get("expect") else []
    return Run(
        passed=not failures if case.get("expect") else None,
        seconds=seconds,
        context_chars=len(messages[-1]["content"]),
        pages=[hit["metadata"]["title"] for hit in retrieved],
        answer=answer,
        failures=failures,
    )


def _cases(extra: Path | None) -> list[dict]:
    cases = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))["cases"]
    if extra:
        lines = extra.read_text(encoding="utf-8").splitlines()
        cases += [
            {"name": f"extra_{i}", "question": line.strip()}
            for i, line in enumerate(lines, 1)
            if line.strip()
        ]
    return cases


def main(modes: list[str], extra: Path | None) -> None:
    totals = {mode: {"passed": 0, "checked": 0, "seconds": 0.0, "chars": 0} for mode in modes}
    cases = _cases(extra)

    for case in cases:
        print(f"\n=== {case['name']}: {case['question']}")
        for mode in modes:
            try:
                run = _run(case, mode)
            except Exception as exc:  # noqa: BLE001 — one failed run must not end the comparison
                print(f"  [{mode}] ОШИБКА: {type(exc).__name__}: {exc}")
                continue

            total = totals[mode]
            total["seconds"] += run.seconds
            total["chars"] += run.context_chars
            if run.passed is not None:
                total["checked"] += 1
                total["passed"] += run.passed

            verdict = {True: "ОК", False: "ПРОВАЛ", None: "—"}[run.passed]
            print(
                f"  [{mode}] {verdict} {run.seconds:.1f}с контекст={run.context_chars} симв. "
                f"страниц={len(run.pages)} {run.pages}"
            )
            for failure in run.failures:
                print(f"         {failure}")
            print(f"         ответ: {run.answer[:400]!r}")

    print("\nИтого:")
    for mode, total in totals.items():
        print(
            f"  {mode:7} golden {total['passed']}/{total['checked']}  "
            f"в среднем {total['seconds'] / len(cases):.1f}с, "
            f"{total['chars'] // len(cases)} симв. контекста"
        )


if __name__ == "__main__":
    # Answers are Russian; a stock Windows console is cp1252.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    parser.add_argument("--modes", nargs="+", default=["off", "select", "digest"])
    parser.add_argument("--extra", type=Path, default=None)
    args = parser.parse_args()
    main(args.modes, args.extra)
