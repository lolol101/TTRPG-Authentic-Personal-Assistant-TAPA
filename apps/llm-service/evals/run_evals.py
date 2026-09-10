"""Runs the golden Q&A set against a live llm-service.

Deliberately not part of pytest: it needs a running service, a configured LLM
provider and network, and it costs tokens. Run it by hand before changing a
prompt or retrieval parameters, per .claude/rules/ml-system-design.md.

    uv run python evals/run_evals.py [--url http://127.0.0.1:8100]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

GOLDEN_PATH = Path(__file__).with_name("golden.json")


def check_case(case: dict, answer: str, sources: list) -> list[str]:
    """Returns a list of failure descriptions; empty means the case passed."""
    expect = case.get("expect", {})
    lowered = answer.lower()
    failures = []

    any_of = expect.get("any_of")
    if any_of and not any(needle.lower() in lowered for needle in any_of):
        failures.append(f"ни одна из подстрок не найдена: {any_of}")

    none_of = expect.get("none_of")
    if none_of:
        present = [needle for needle in none_of if needle.lower() in lowered]
        if present:
            failures.append(f"найдены запрещённые подстроки: {present}")

    if expect.get("sources_non_empty") and not sources:
        failures.append("ответ без источников")

    return failures


def run(url: str) -> int:
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    cases = golden["cases"]
    failed = 0

    for case in cases:
        body = {"question": case["question"]}
        if case.get("character_context"):
            body["character_context"] = case["character_context"]

        try:
            response = httpx.post(f"{url}/ask", json=body, timeout=120.0)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            print(f"[ОШИБКА] {case['name']}: запрос не прошёл — {exc}")
            failed += 1
            continue

        payload = response.json()
        answer = payload.get("answer", "")
        failures = check_case(case, answer, payload.get("sources", []))

        if failures:
            failed += 1
            print(f"[ПРОВАЛ] {case['name']}")
            for failure in failures:
                print(f"         {failure}")
            print(f"         ответ: {answer[:300]}")
        else:
            print(f"[ОК]     {case['name']}")

    print(f"\nИтого: {len(cases) - failed}/{len(cases)} пройдено")
    return 1 if failed else 0


if __name__ == "__main__":
    # Cases and answers are Russian; a stock Windows console is cp1252 and
    # would crash on the first printed result.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8100")
    sys.exit(run(parser.parse_args().url))
