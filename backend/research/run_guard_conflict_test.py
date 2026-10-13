"""Evaluate conflict surfacing on the synthetic 40-case G-09 set."""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

from backend.research.guard.conflict import ConflictThresholds, detect_conflicts
from backend.research.guard.nli import MODEL_CACHE, MultilingualNLIScorer
from backend.research.run_guard_nli_test import MalayalamToEnglish

ROOT = Path(__file__).parent
CASES_PATH = ROOT / "guard" / "conflict_cases.jsonl"
THRESHOLDS_PATH = ROOT / "guard" / "thresholds.json"


def _metrics(actual: list[bool], predicted: list[bool]) -> tuple[int, int, int, int, float, float]:
    tp = sum(a and p for a, p in zip(actual, predicted))
    fp = sum(not a and p for a, p in zip(actual, predicted))
    fn = sum(a and not p for a, p in zip(actual, predicted))
    tn = sum(not a and not p for a, p in zip(actual, predicted))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return tp, fp, fn, tn, precision, recall


def main() -> int:
    cases = [
        json.loads(line)
        for line in CASES_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    config = json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))
    scorer = MultilingualNLIScorer(device="cpu")
    translator = MalayalamToEnglish(device="cpu")
    predictions: dict[str, list[bool]] = {"en": [], "ml": []}
    actual: dict[str, list[bool]] = {"en": [], "ml": []}
    type_counts: dict[str, int] = {}

    for case in cases:
        lang = case["lang"]
        option = "pivot" if lang == "ml" else "direct"
        raw_thresholds = config["results"][option][lang]
        thresholds = ConflictThresholds(
            raw_thresholds["entailment"], raw_thresholds["contradiction"]
        )

        def transform_claim(text: str) -> str:
            if lang == "ml" and any("\u0d00" <= char <= "\u0d7f" for char in text):
                return translator.translate(text)
            return text

        found = detect_conflicts(
            case["answer"],
            case["context"],
            case["instructions"],
            lang,
            scorer,
            thresholds,
            claim_transform=transform_claim,
        )
        predictions[lang].append(bool(found))
        actual[lang].append(bool(case["expected_conflicts"]))
        for conflict in found:
            type_counts[conflict["type"]] = type_counts.get(conflict["type"], 0) + 1

    print(f"Cases: {len(cases)}")
    failed = False
    for lang, label in (("en", "English"), ("ml", "Malayalam")):
        tp, fp, fn, tn, precision, recall = _metrics(actual[lang], predictions[lang])
        print(
            f"{label}: TP={tp} FP={fp} FN={fn} TN={tn} "
            f"precision={precision:.3f} recall={recall:.3f}"
        )
        failed |= tp + fp == 0 or tp + fn == 0
    tp, fp, fn, tn, precision, recall = _metrics(
        actual["en"] + actual["ml"], predictions["en"] + predictions["ml"]
    )
    print(
        f"Overall: TP={tp} FP={fp} FN={fn} TN={tn} "
        f"precision={precision:.3f} recall={recall:.3f}"
    )
    print(f"Predicted conflict types: {type_counts}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
