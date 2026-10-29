"""English redaction policy applied after the frozen claim verdict."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActionPolicy:
    name: str
    contradiction_min: float | None
    neutral_min: float | None
    entailment_max: float | None
    allow_exact: bool


BASELINE = ActionPolicy("baseline", None, None, None, True)
# Set only after the train-development and reserved-validation gates pass.
ACTIVE_ENGLISH = BASELINE


def should_alter(verdict: str, scores: object, exact_verdict: str | None, policy: ActionPolicy) -> bool:
    if verdict not in {"supported", "unsupported", "contradicted"}:
        raise ValueError(f"Unknown verdict: {verdict}")
    if verdict == "supported":
        return False
    if policy == BASELINE:
        return True
    if exact_verdict is not None and not policy.allow_exact:
        return False
    if verdict == "contradicted":
        return (policy.contradiction_min is not None
                and scores.contradiction >= policy.contradiction_min
                and scores.contradiction > scores.entailment)
    return (policy.neutral_min is not None
            and scores.neutral >= policy.neutral_min
            and (policy.entailment_max is None or scores.entailment <= policy.entailment_max))
