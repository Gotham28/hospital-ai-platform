"""Local natural-language-inference scoring for guard claims."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

MODEL_ID = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
MODEL_CACHE = Path(__file__).resolve().parents[2] / "venv" / "model_cache"
_DIGIT_TRANSLATION = str.maketrans("൦൧൨൩൪൫൬൭൮൯", "0123456789")
_NUMBER = re.compile(r"(?<!\w)(\d+(?::\d+)?(?:\.\d+)?)(?!\w)")
_PRICE = re.compile(r"₹|\brs\.?\b|\brupees?\b|രൂപ|ഫീസ്|വില|ചെലവ്", re.I)
_TIME = re.compile(r":|\b(?:am|pm|o'clock)\b|മണി|രാവിലെ|ഉച്ചയ്ക്ക്|വൈകുന്നേരം", re.I)
_DURATION = re.compile(r"\b(?:days?|weeks?|hours?)\b|ദിവസം|മണിക്കൂർ", re.I)


@dataclass(frozen=True)
class NLIScores:
    entailment: float
    neutral: float
    contradiction: float


@dataclass(frozen=True)
class ClaimAssessment:
    verdict: str
    scores: NLIScores
    evidence: str | None
    exact_verdict: str | None = None


def _typed_values(text: str) -> dict[str, set[str]]:
    normalized = text.translate(_DIGIT_TRANSLATION).casefold()
    result: dict[str, set[str]] = {"price": set(), "time": set(), "duration": set()}
    for match in _NUMBER.finditer(normalized):
        nearby = normalized[max(0, match.start() - 24) : match.end() + 24]
        if _PRICE.search(nearby):
            kind = "price"
        elif _TIME.search(nearby):
            kind = "time"
        elif _DURATION.search(nearby):
            kind = "duration"
        else:
            continue
        result[kind].add(match.group(1))
    return result


class MultilingualNLIScorer:
    """Score premise/hypothesis pairs with a locally cached Transformers model."""

    def __init__(
        self,
        model_id: str = MODEL_ID,
        batch_size: int = 8,
        cache_dir: Path = MODEL_CACHE,
        device: str | None = None,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self._torch = torch
        self._tokenizer = AutoTokenizer.from_pretrained(
            model_id, cache_dir=cache_dir
        )
        self._model = AutoModelForSequenceClassification.from_pretrained(
            model_id, cache_dir=cache_dir
        )
        selected_device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.device = torch.device(selected_device)
        target_dtype = torch.float32 if self.device.type == "cpu" else torch.float16
        self._model.to(device=self.device, dtype=target_dtype)
        self._model.eval()
        self.batch_size = batch_size
        labels = {
            int(index): str(label).casefold()
            for index, label in self._model.config.id2label.items()
        }
        self._label_indices = {
            name: next(
                (index for index, label in labels.items() if name in label), None
            )
            for name in ("entailment", "neutral", "contradiction")
        }
        if any(index is None for index in self._label_indices.values()):
            raise ValueError(
                "The model config must name entailment, neutral, and contradiction labels"
            )

    def score_pairs(self, pairs: Iterable[tuple[str, str]]) -> list[NLIScores]:
        pair_list = list(pairs)
        results: list[NLIScores] = []
        for start in range(0, len(pair_list), self.batch_size):
            batch = pair_list[start : start + self.batch_size]
            encoded = self._tokenizer(
                [premise for premise, _ in batch],
                [hypothesis for _, hypothesis in batch],
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True,
            )
            encoded = {key: value.to(self.device) for key, value in encoded.items()}
            with self._torch.inference_mode():
                probabilities = self._torch.softmax(
                    self._model(**encoded).logits, dim=-1
                ).cpu()
            for row in probabilities:
                results.append(
                    NLIScores(
                        entailment=float(row[self._label_indices["entailment"]]),
                        neutral=float(row[self._label_indices["neutral"]]),
                        contradiction=float(
                            row[self._label_indices["contradiction"]]
                        ),
                    )
                )
        return results

    def assess(
        self,
        claim: str,
        context: list[str],
        *,
        entailment_threshold: float,
        contradiction_threshold: float,
    ) -> ClaimAssessment:
        """Choose the strongest evidence across passages using fixed thresholds."""
        if not 0.0 <= entailment_threshold <= 1.0:
            raise ValueError("entailment_threshold must be between 0 and 1")
        if not 0.0 <= contradiction_threshold <= 1.0:
            raise ValueError("contradiction_threshold must be between 0 and 1")
        if not context:
            return ClaimAssessment(
                "unsupported", NLIScores(0.0, 1.0, 0.0), None
            )

        claim_values = _typed_values(claim)
        context_values = [_typed_values(passage) for passage in context]
        exact_verdict: str | None = None
        exact_evidence: str | None = None
        for kind, values in claim_values.items():
            if not values:
                continue
            for passage, passage_values in zip(context, context_values):
                expected = passage_values[kind]
                if expected and values.isdisjoint(expected):
                    exact_verdict, exact_evidence = "contradicted", passage
                    break
            if exact_verdict:
                break
        if any(claim_values.values()) and not any(
            values for passage_values in context_values for values in passage_values.values()
        ):
            exact_verdict = "unsupported"

        scores = self.score_pairs((passage, claim) for passage in context)
        best_index = max(
            range(len(scores)),
            key=lambda index: max(
                scores[index].entailment, scores[index].contradiction
            ),
        )
        best = scores[best_index]
        if (
            best.contradiction >= contradiction_threshold
            and best.contradiction > best.entailment
        ):
            verdict = "contradicted"
        elif best.entailment >= entailment_threshold:
            verdict = "supported"
        else:
            verdict = "unsupported"
        if exact_verdict is not None:
            verdict = exact_verdict
        evidence = exact_evidence or context[best_index]
        return ClaimAssessment(verdict, best, evidence, exact_verdict)
