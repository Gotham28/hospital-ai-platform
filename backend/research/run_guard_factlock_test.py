"""Evaluate fact-lock extraction on the synthetic 40-case G-10 set."""

from __future__ import annotations

import json
from pathlib import Path

from backend.research.guard.factlock import compare_fact_locks

CASES_PATH = Path(__file__).parent / "guard" / "factlock_cases.jsonl"


def main() -> int:
    cases = [
        json.loads(line)
        for line in CASES_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    correct = 0
    misses: list[tuple[str, str, list[str]]] = []
    for case in cases:
        actual = [
            entry["status"]
            for entry in compare_fact_locks(case["context"], case["answer"])
            if entry["type"] == case["target_type"]
        ]
        if actual == [case["expected"]]:
            correct += 1
        else:
            misses.append((case["id"], case["expected"], actual))

    print(f"Cases handled correctly: {correct}/{len(cases)}")
    if misses:
        print("Misses (id, expected, actual):")
        for miss in misses:
            print(f"{miss[0]}: expected={miss[1]} actual={miss[2]}")
    if correct < 36:
        print("FAIL: fewer than 36 of 40 cases were handled correctly")
        return 1
    print("PASS: at least 36 of 40 cases were handled correctly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
