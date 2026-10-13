"""Part D evaluation module for AROGYA hospital RAG benchmarks.

Measures error reduction, the English-Malayalam performance gap before and after
applying the guard, and component ablations.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from backend.research.baselines.rarr_style import apply_baseline
from backend.research.guard.guard import GuardOptions, apply_guard_with_options


@dataclass(frozen=True)
class PartDMetrics:
    total_answers: int
    en_total: int
    ml_total: int
    en_errors_before: int
    en_errors_after_guard: int
    ml_errors_before: int
    ml_errors_after_guard: int
    en_error_rate_before: float
    en_error_rate_after: float
    ml_error_rate_before: float
    ml_error_rate_after: float
    gap_before: float
    gap_after: float
    false_alteration_count: int  # guard changed an already correct/supported answer


def evaluate_part_d(items: list[dict[str, Any]]) -> PartDMetrics:
    en_total = sum(1 for x in items if x.get("lang") == "en")
    ml_total = sum(1 for x in items if x.get("lang") == "ml")

    en_errors_before = 0
    en_errors_after = 0
    ml_errors_before = 0
    ml_errors_after = 0
    false_alterations = 0

    for item in items:
        lang = item.get("lang", "en")
        verdict = item.get("ground_truth", {}).get("overall_verdict", "supported")
        is_error_before = verdict in {"unsupported", "contradicted"}

        if lang == "en" and is_error_before:
            en_errors_before += 1
        elif lang == "ml" and is_error_before:
            ml_errors_before += 1

        answer = item.get("answer", "")
        context = item.get("context", [])
        instructions = item.get("instructions", "")

        guard_res = apply_guard_with_options(
            answer,
            context,
            instructions,
            lang,
            options=GuardOptions(claim_check=True, conflict_surfacing=True, fact_lock=True),
        )

        changed = guard_res["changed"]

        # If it was supported, did the guard wrongly alter it?
        if not is_error_before and changed:
            false_alterations += 1

        # If it had an error before, was it successfully intercepted/redacted?
        is_error_after = is_error_before and not changed
        if lang == "en" and is_error_after:
            en_errors_after += 1
        elif lang == "ml" and is_error_after:
            ml_errors_after += 1

    en_rate_before = (en_errors_before / en_total) if en_total else 0.0
    en_rate_after = (en_errors_after / en_total) if en_total else 0.0
    ml_rate_before = (ml_errors_before / ml_total) if ml_total else 0.0
    ml_rate_after = (ml_errors_after / ml_total) if ml_total else 0.0

    gap_before = ml_rate_before - en_rate_before
    gap_after = ml_rate_after - en_rate_after

    return PartDMetrics(
        total_answers=len(items),
        en_total=en_total,
        ml_total=ml_total,
        en_errors_before=en_errors_before,
        en_errors_after_guard=en_errors_after,
        ml_errors_before=ml_errors_before,
        ml_errors_after_guard=ml_errors_after,
        en_error_rate_before=en_rate_before,
        en_error_rate_after=en_rate_after,
        ml_error_rate_before=ml_rate_before,
        ml_error_rate_after=ml_rate_after,
        gap_before=gap_before,
        gap_after=gap_after,
        false_alteration_count=false_alterations,
    )
