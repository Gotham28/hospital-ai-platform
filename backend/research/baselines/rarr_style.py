"""A local context-only adaptation of RARR for public evaluation.

This module is deliberately separate from ``backend.research.guard``. It is a
comparison baseline, not a component of the proposed grounding guard.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import TypedDict


_SENTENCES = re.compile(r"(?<=[.!?])\s+|\n+")
_TOKENS = re.compile(r"[a-z0-9]+")
_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
    "is", "it", "of", "on", "or", "that", "the", "to", "was", "with",
}


class BaselineResult(TypedDict):
    """Result shape compatible with the grounding guard's fixed interface."""

    final_answer: str
    claims: list[dict[str, str]]
    conflicts: list[dict[str, str]]
    fact_lock: list[dict[str, str]]
    changed: bool


@dataclass(frozen=True)
class Attribution:
    claim: str
    evidence: str | None
    supported: bool


def _claim_sentences(answer: str) -> list[str]:
    return [sentence.strip() for sentence in _SENTENCES.split(answer) if sentence.strip()]


def _content_tokens(text: str) -> set[str]:
    return {token for token in _TOKENS.findall(text.casefold()) if token not in _STOP_WORDS}


def attribute_claim(claim: str, context: list[str]) -> Attribution:
    """Find the strongest supplied-context attribution for one English claim.

    RARR's original research stage obtains evidence from web search. The G-12
    adaptation is restricted to the retrieved passages supplied to the public
    evaluation, so both methods see identical evidence.
    """

    claim_tokens = _content_tokens(claim)
    if not claim_tokens:
        return Attribution(claim, None, False)

    best_evidence: str | None = None
    best_overlap = 0
    for passage in context:
        overlap = len(claim_tokens & _content_tokens(passage))
        if overlap > best_overlap:
            best_evidence = passage
            best_overlap = overlap

    supported = best_overlap == len(claim_tokens)
    return Attribution(claim, best_evidence, supported)


def apply_baseline(
    answer: str,
    context: list[str],
    instructions: str,
    lang: str,
) -> BaselineResult:
    """Apply local attribution then redact claims without full lexical support.

    ``instructions`` is accepted to preserve the guard interface. This baseline
    does not use instructions because the published RARR workflow attributes and
    revises generated claims against evidence rather than resolving
    instruction-versus-data conflicts.
    """

    if lang != "en":
        raise ValueError("The G-12 RARR-style baseline currently supports English only")
    if not isinstance(answer, str) or not isinstance(context, list) or not isinstance(instructions, str):
        raise TypeError("answer, context, and instructions must be strings/list[str]")
    if not all(isinstance(passage, str) for passage in context):
        raise TypeError("context must contain only strings")

    final_answer = answer
    claims: list[dict[str, str]] = []
    for claim in _claim_sentences(answer):
        attribution = attribute_claim(claim, context)
        verdict = "supported" if attribution.supported else "unsupported"
        claims.append(
            {
                "text": claim,
                "verdict": verdict,
                "evidence": attribution.evidence or "None",
            }
        )
        if not attribution.supported:
            final_answer = final_answer.replace(claim, "[FLAG_TEXT]", 1)

    return {
        "final_answer": final_answer,
        "claims": claims,
        "conflicts": [],
        "fact_lock": [],
        "changed": final_answer != answer,
    }


apply_guard = apply_baseline
