"""Evaluation pipeline for the G-13 public-dataset experiment.

Applies the proposed grounding guard, its ablations, and the G-12 comparison baseline
to saved or generated answers across the fixed 300 RAGTruth sample.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from backend.research.baselines.rarr_style import apply_baseline
from backend.research.guard.guard import GuardOptions, apply_guard_with_options
from backend.research.public_eval.loader import PublicEvalItem


@dataclass(frozen=True)
class EvaluationSummary:
    total_items: int
    raw_unchanged_count: int
    baseline_changed_count: int
    guard_full_changed_count: int
    guard_no_claims_changed_count: int
    guard_no_conflicts_changed_count: int
    guard_no_factlock_changed_count: int


def evaluate_items(
    items: list[PublicEvalItem],
    answers: dict[str, str],
    output_dir: Path | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], EvaluationSummary]:
    """Apply No-Guard, Baseline, Full Guard, and 3 Guard ablations to answers."""
    results: dict[str, list[dict[str, Any]]] = {
        "no_guard": [],
        "baseline": [],
        "guard_full": [],
        "guard_no_claims": [],
        "guard_no_conflicts": [],
        "guard_no_factlock": [],
    }

    baseline_changed = 0
    guard_full_changed = 0
    guard_no_claims_changed = 0
    guard_no_conflicts_changed = 0
    guard_no_factlock_changed = 0

    for item in items:
        answer = answers.get(item.question_id, "")
        instructions = item.prompt
        context = item.context
        lang = "en"

        # 1. No guard
        results["no_guard"].append(
            {
                "question_id": item.question_id,
                "answer": answer,
                "changed": False,
            }
        )

        # 2. Baseline (RARR-style)
        base_res = apply_baseline(answer, context, instructions, lang)
        if base_res["changed"]:
            baseline_changed += 1
        results["baseline"].append(
            {
                "question_id": item.question_id,
                "answer": base_res["final_answer"],
                "changed": base_res["changed"],
                "claims": base_res["claims"],
            }
        )

        # 3. Guard Full
        full_res = apply_guard_with_options(
            answer,
            context,
            instructions,
            lang,
            options=GuardOptions(claim_check=True, conflict_surfacing=True, fact_lock=True),
        )
        if full_res["changed"]:
            guard_full_changed += 1
        results["guard_full"].append(
            {
                "question_id": item.question_id,
                "answer": full_res["final_answer"],
                "changed": full_res["changed"],
                "claims": full_res["claims"],
                "conflicts": full_res["conflicts"],
                "fact_lock": full_res["fact_lock"],
            }
        )

        # 4. Guard Ablation: No claims
        no_claims_res = apply_guard_with_options(
            answer,
            context,
            instructions,
            lang,
            options=GuardOptions(claim_check=False, conflict_surfacing=True, fact_lock=True),
        )
        if no_claims_res["changed"]:
            guard_no_claims_changed += 1
        results["guard_no_claims"].append(
            {
                "question_id": item.question_id,
                "answer": no_claims_res["final_answer"],
                "changed": no_claims_res["changed"],
            }
        )

        # 5. Guard Ablation: No conflicts
        no_conf_res = apply_guard_with_options(
            answer,
            context,
            instructions,
            lang,
            options=GuardOptions(claim_check=True, conflict_surfacing=False, fact_lock=True),
        )
        if no_conf_res["changed"]:
            guard_no_conflicts_changed += 1
        results["guard_no_conflicts"].append(
            {
                "question_id": item.question_id,
                "answer": no_conf_res["final_answer"],
                "changed": no_conf_res["changed"],
            }
        )

        # 6. Guard Ablation: No fact-lock
        no_lock_res = apply_guard_with_options(
            answer,
            context,
            instructions,
            lang,
            options=GuardOptions(claim_check=True, conflict_surfacing=True, fact_lock=False),
        )
        if no_lock_res["changed"]:
            guard_no_factlock_changed += 1
        results["guard_no_factlock"].append(
            {
                "question_id": item.question_id,
                "answer": no_lock_res["final_answer"],
                "changed": no_lock_res["changed"],
            }
        )

    summary = EvaluationSummary(
        total_items=len(items),
        raw_unchanged_count=len(items),
        baseline_changed_count=baseline_changed,
        guard_full_changed_count=guard_full_changed,
        guard_no_claims_changed_count=guard_no_claims_changed,
        guard_no_conflicts_changed_count=guard_no_conflicts_changed,
        guard_no_factlock_changed_count=guard_no_factlock_changed,
    )

    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        for cond, rows in results.items():
            path = output_dir / f"public_eval_{cond}.jsonl"
            with path.open("w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    return results, summary
