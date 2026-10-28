"""Append-only resumable cache for NLI premise/hypothesis scores."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.research.guard.nli import NLIScores

DEFAULT_MODEL_REVISION = "8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c"


def make_key(passage: str, claim: str, model_revision: str = DEFAULT_MODEL_REVISION) -> str:
    """Compute sha256 key over model_revision + passage + claim."""
    data = (model_revision + passage + claim).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


class NLICache:
    """Thread-safe append-only JSONL cache for NLI pair scores."""

    def __init__(
        self,
        cache_path: str | Path,
        *,
        model_revision: str = DEFAULT_MODEL_REVISION,
        flush_every: int = 50,
    ) -> None:
        self.cache_path = Path(cache_path)
        self.model_revision = model_revision
        self.flush_every = flush_every
        self._entries: dict[str, dict[str, Any]] = {}
        self._pending_writes = 0
        self._file = None

        self._load_existing()

    def _load_existing(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        if self.cache_path.exists():
            with self.cache_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        k = record["key"]
                        self._entries[k] = record
                    except (json.JSONDecodeError, KeyError):
                        continue

    def _open_file_if_needed(self):
        if self._file is None:
            self._file = self.cache_path.open("a", encoding="utf-8")
        return self._file

    def get(self, key: str) -> NLIScores | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        s = entry["scores"]
        return NLIScores(
            entailment=float(s["entailment"]),
            neutral=float(s["neutral"]),
            contradiction=float(s["contradiction"]),
        )

    def set(
        self,
        key: str,
        scores: NLIScores,
        *,
        answer_id: str | None = None,
        claim_index: int | None = None,
        passage_index: int | None = None,
    ) -> None:
        record: dict[str, Any] = {
            "key": key,
            "scores": {
                "entailment": float(scores.entailment),
                "neutral": float(scores.neutral),
                "contradiction": float(scores.contradiction),
            },
            "answer_id": str(answer_id) if answer_id is not None else None,
            "claim_index": claim_index,
            "passage_index": passage_index,
        }
        self._entries[key] = record

        f = self._open_file_if_needed()
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._pending_writes += 1
        if self._pending_writes >= self.flush_every:
            self.flush()

    def flush(self) -> None:
        if self._file is not None:
            self._file.flush()
            self._pending_writes = 0

    def close(self) -> None:
        if self._file is not None:
            self._file.flush()
            self._file.close()
            self._file = None
            self._pending_writes = 0

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, key: str) -> bool:
        return key in self._entries
