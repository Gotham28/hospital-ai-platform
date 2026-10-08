"""Conflict surfacing for data, instructions, and generated answers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .claims import split_claims
from .nli import ClaimAssessment, MultilingualNLIScorer


@dataclass(frozen=True)
class ConflictThresholds:
    entailment: float
    contradiction: float


def _assess(
    text: str,
    context: list[str],
    scorer: MultilingualNLIScorer,
    thresholds: ConflictThresholds,
) -> ClaimAssessment:
    return scorer.assess(
        text,
        context,
        entailment_threshold=thresholds.entailment,
        contradiction_threshold=thresholds.contradiction,
    )


def detect_conflicts(
    answer: str,
    context: list[str],
    instructions: str,
    lang: str,
    scorer: MultilingualNLIScorer,
    thresholds: ConflictThresholds,
    claim_transform: Callable[[str], str] | None = None,
) -> list[dict[str, str]]:
    """Return clashes between instructions/data and answer/data.

    Instruction/data clashes are reported before answer attribution. A
    contradicted answer claim that is supported by an instruction is attributed
    to that instruction; otherwise it is attributed to the answer.
    """
    conflicts: list[dict[str, str]] = []
    instruction_claims = split_claims(instructions, lang)
    answer_claims = split_claims(answer, lang)

    for instruction_claim in instruction_claims:
        model_instruction = (
            claim_transform(instruction_claim)
            if claim_transform is not None
            else instruction_claim
        )
        instruction_check = _assess(
            model_instruction, context, scorer, thresholds
        )
        if instruction_check.verdict == "contradicted":
            conflicts.append(
                {
                    "type": "instruction_vs_data",
                    "text_a": instruction_claim,
                    "text_b": instruction_check.evidence or "",
                    "evidence": instruction_check.evidence or "",
                }
            )

    for answer_claim in answer_claims:
        model_answer = (
            claim_transform(answer_claim)
            if claim_transform is not None
            else answer_claim
        )
        data_check = _assess(model_answer, context, scorer, thresholds)
        if data_check.verdict != "contradicted":
            continue
        instruction_check = _assess(
            model_answer,
            [
                claim_transform(claim)
                if claim_transform is not None
                else claim
                for claim in instruction_claims
            ],
            scorer,
            thresholds,
        ) if instruction_claims else None
        conflict_type = (
            "answer_follows_instruction_against_data"
            if instruction_check is not None
            and instruction_check.verdict == "supported"
            else "answer_vs_data"
        )
        conflicts.append(
            {
                "type": conflict_type,
                "text_a": answer_claim,
                "text_b": data_check.evidence or "",
                "evidence": data_check.evidence or "",
            }
        )

    unique: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for conflict in conflicts:
        key = (conflict["type"], conflict["text_a"], conflict["text_b"])
        if key not in seen:
            unique.append(conflict)
            seen.add(key)
    return unique
