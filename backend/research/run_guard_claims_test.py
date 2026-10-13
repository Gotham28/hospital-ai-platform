"""Measure claim-splitting recall against the tuning half of the dev set."""

from __future__ import annotations

import json
import re
from pathlib import Path

from backend.research.guard.claims import split_claims

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "guard_dev_set.json"


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


def _recall_for_language(items: list[dict], lang: str) -> tuple[int, int]:
    found = total = 0
    for item in items:
        if item["lang"] != lang:
            continue
        predicted = [_normalize(claim) for claim in split_claims(item["answer"], lang)]
        used: set[int] = set()
        for gold in item["ground_truth"]["claims"]:
            total += 1
            target = _normalize(gold["text"])
            match = next(
                (
                    index
                    for index, claim in enumerate(predicted)
                    if index not in used and (target in claim or claim in target)
                ),
                None,
            )
            if match is not None:
                used.add(match)
                found += 1
    return found, total


def main() -> int:
    items = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    tuning = [item for item in items if item["split"] == "tuning"]
    failed = False
    for lang, label in (("en", "English"), ("ml", "Malayalam")):
        found, total = _recall_for_language(tuning, lang)
        recall = found / total if total else 0.0
        print(f"{label} tuning facts found: {found}/{total} ({recall:.1%})")
        failed |= recall < 0.85
    if failed:
        print("FAIL: claim recall is below 85% for at least one language")
        return 1
    print("PASS: claim recall is at least 85% in both languages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
