"""Cached subclass of MultilingualNLIScorer supporting strict and fill modes."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from backend.research.guard.nli import MODEL_CACHE, MODEL_ID, MultilingualNLIScorer, NLIScores
from backend.research.replay.cache import DEFAULT_MODEL_REVISION, NLICache, make_key


class CachedScorer(MultilingualNLIScorer):
    """Subclass of MultilingualNLIScorer backed by an append-only score cache.

    Modes:
      - 'strict': Only serves from cache. Raises KeyError on any cache miss.
                  Avoids loading model weights into memory.
      - 'fill': Loads the pinned model. On cache miss, scores the pair with the
                model, writes to cache (JSONL), flushes, and returns scores.
    """

    def __init__(
        self,
        cache: NLICache | str | Path,
        *,
        mode: str = "strict",
        batch_size: int = 16,
        model_id: str = MODEL_ID,
        cache_dir: Path = MODEL_CACHE,
        device: str | None = None,
        model_revision: str = DEFAULT_MODEL_REVISION,
    ) -> None:
        if mode not in {"strict", "fill"}:
            raise ValueError(f"Unknown mode: {mode}. Must be 'strict' or 'fill'.")
        self.mode = mode
        self.model_revision = model_revision
        self.batch_size = batch_size

        if isinstance(cache, NLICache):
            self.cache = cache
        else:
            self.cache = NLICache(cache, model_revision=model_revision)

        if mode == "fill":
            super().__init__(
                model_id=model_id,
                batch_size=batch_size,
                cache_dir=cache_dir,
                device=device,
            )
        else:
            # In strict mode, do not load torch weights into memory
            self._model = None
            self._tokenizer = None

    def score_pairs(self, pairs: Iterable[tuple[str, str]]) -> list[NLIScores]:
        pair_list = list(pairs)
        results: list[NLIScores | None] = [None] * len(pair_list)
        missing_indices: list[int] = []
        missing_pairs: list[tuple[str, str]] = []
        missing_keys: list[str] = []

        for idx, (passage, claim) in enumerate(pair_list):
            key = make_key(passage, claim, self.model_revision)
            cached_scores = self.cache.get(key)
            if cached_scores is not None:
                results[idx] = cached_scores
            else:
                if self.mode == "strict":
                    raise KeyError(
                        f"Cache miss in strict mode for key {key} (claim={claim[:40]!r}, passage={passage[:40]!r})"
                    )
                missing_indices.append(idx)
                missing_pairs.append((passage, claim))
                missing_keys.append(key)

        if missing_pairs:
            # Score missing pairs with model
            computed_scores = super().score_pairs(missing_pairs)
            for idx, key, (passage, claim), score in zip(
                missing_indices, missing_keys, missing_pairs, computed_scores
            ):
                self.cache.set(key, score)
                results[idx] = score

        return [res for res in results if res is not None]
