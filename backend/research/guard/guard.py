"""End-to-end research guard assembly; not wired into the production app."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import TypedDict

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

from .action_policy import ACTIVE_ENGLISH, should_alter
from .claims import split_claims
from .conflict import ConflictThresholds, detect_conflicts
from .factlock import compare_fact_locks
from .nli import MODEL_CACHE, MultilingualNLIScorer

_ROOT = Path(__file__).resolve().parents[1]
_THRESHOLDS_PATH = Path(__file__).with_name("thresholds.json")
_SCORER: MultilingualNLIScorer | None = None
_TRANSLATOR = None


class GuardResult(TypedDict):
    final_answer: str
    claims: list[dict[str, object]]
    conflicts: list[dict[str, str]]
    fact_lock: list[dict[str, str]]
    changed: bool


@dataclass(frozen=True)
class GuardOptions:
    claim_check: bool = True
    conflict_surfacing: bool = True
    fact_lock: bool = True


def _scorer() -> MultilingualNLIScorer:
    global _SCORER
    if _SCORER is None:
        _SCORER = MultilingualNLIScorer(device="cpu")
    return _SCORER


def _translator():
    global _TRANSLATOR
    if _TRANSLATOR is None:
        from backend.research.run_guard_nli_test import MalayalamToEnglish

        _TRANSLATOR = MalayalamToEnglish(device="cpu")
    return _TRANSLATOR


def _thresholds(lang: str) -> tuple[str, ConflictThresholds]:
    if not _THRESHOLDS_PATH.exists():
        raise FileNotFoundError(
            f"Calibrated thresholds are missing: {_THRESHOLDS_PATH}"
        )
    config = json.loads(_THRESHOLDS_PATH.read_text(encoding="utf-8"))
    option = "pivot" if lang == "ml" else "direct"
    values = config["results"][option][lang]
    return option, ConflictThresholds(
        entailment=values["entailment"],
        contradiction=values["contradiction"],
    )


def apply_guard_with_options(
    answer: str,
    context: list[str],
    instructions: str,
    lang: str,
    *,
    options: GuardOptions,
) -> GuardResult:
    """Run selected components, allowing research ablations per component."""
    if lang not in {"en", "ml"}:
        raise ValueError("lang must be 'en' or 'ml'")
    final_answer = answer
    claims: list[dict[str, object]] = []
    conflicts: list[dict[str, str]] = []
    fact_lock: list[dict[str, str]] = []

    if options.claim_check or options.conflict_surfacing:
        scorer = _scorer()
        option, thresholds = _thresholds(lang)

        def transform_claim(text: str) -> str:
            if option == "pivot" and any("\u0d00" <= char <= "\u0d7f" for char in text):
                return _translator().translate(text)
            return text

        if options.claim_check:
            for claim in split_claims(answer, lang):
                assessment = scorer.assess(
                    transform_claim(claim),
                    context,
                    entailment_threshold=thresholds.entailment,
                    contradiction_threshold=thresholds.contradiction,
                )
                action = (should_alter(assessment.verdict, assessment.scores, assessment.exact_verdict, ACTIVE_ENGLISH)
                          if lang == "en" else assessment.verdict in {"unsupported", "contradicted"})
                claim_result: dict[str, object] = {
                        "text": claim,
                        "verdict": assessment.verdict,
                        "evidence": assessment.evidence or "None",
                    }
                if lang == "en":
                    claim_result["altered"] = action
                claims.append(claim_result)
                if action:
                    final_answer = final_answer.replace(claim, "[FLAG_TEXT]")

        if options.conflict_surfacing:
            conflicts = detect_conflicts(
                answer,
                context,
                instructions,
                lang,
                scorer,
                thresholds,
                claim_transform=transform_claim,
            )

    if options.fact_lock:
        fact_lock = compare_fact_locks(context, answer)

    return {
        "final_answer": final_answer,
        "claims": claims,
        "conflicts": conflicts,
        "fact_lock": fact_lock,
        "changed": final_answer != answer,
    }


def apply_guard(
    answer: str,
    context: list[str],
    instructions: str,
    lang: str,
) -> GuardResult:
    """Apply claim checks, conflict surfacing, and fact-lock checks."""
    return apply_guard_with_options(
        answer,
        context,
        instructions,
        lang,
        options=GuardOptions(),
    )
