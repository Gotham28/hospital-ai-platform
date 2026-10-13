"""Load a reproducible public-evaluation sample from RAGTruth.

Download the RAGTruth repository separately and pass its ``dataset`` directory
to :func:`load_ragtruth_qa_test_items`. The dataset is deliberately not stored
in this repository.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import random
import re
from typing import Any


RAGTRUTH_DATASET_URL = "https://github.com/ParticleMedia/RAGTruth"
DEFAULT_SAMPLE_SIZE = 300
DEFAULT_SAMPLE_SEED = 20261007


@dataclass(frozen=True)
class PublicEvalItem:
    """One question and its retrieved context for a public evaluation run."""

    question_id: str
    question: str
    context: list[str]
    prompt: str
    source_id: str


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Expected {path}. Download RAGTruth from {RAGTRUTH_DATASET_URL} "
            "and pass its dataset directory."
        )

    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path} at line {line_number}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"Expected an object in {path} at line {line_number}")
            records.append(record)
    return records


def _split_passages(passages: str) -> list[str]:
    """Preserve RAGTruth passage boundaries when they are present."""

    pieces = re.split(r"(?=\bpassage\s+\d+\s*:)", passages, flags=re.IGNORECASE)
    return [piece.strip() for piece in pieces if piece.strip()]


def load_ragtruth_qa_test_items(dataset_dir: Path) -> list[PublicEvalItem]:
    """Load QA source records that have at least one usable test response.

    RAGTruth provides source records and generated responses separately. This
    function selects source records referenced by a ``test`` response whose
    quality is ``good``; it does not copy responses or labels into this project.
    """

    source_records = _read_jsonl(dataset_dir / "source_info.jsonl")
    response_records = _read_jsonl(dataset_dir / "response.jsonl")

    usable_source_ids = {
        str(response["source_id"])
        for response in response_records
        if response.get("split") == "test"
        and response.get("quality") == "good"
        and response.get("source_id") is not None
    }

    items: list[PublicEvalItem] = []
    for source in source_records:
        if source.get("task_type") != "QA" or str(source.get("source_id")) not in usable_source_ids:
            continue
        source_info = source.get("source_info")
        if not isinstance(source_info, dict):
            continue
        question = source_info.get("question")
        passages = source_info.get("passages")
        prompt = source.get("prompt")
        if not isinstance(question, str) or not isinstance(passages, str) or not isinstance(prompt, str):
            continue
        context = _split_passages(passages)
        if context:
            source_id = str(source["source_id"])
            items.append(
                PublicEvalItem(
                    question_id=f"ragtruth-qa-{source_id}",
                    question=question,
                    context=context,
                    prompt=prompt,
                    source_id=source_id,
                )
            )

    if not items:
        raise ValueError("No usable RAGTruth QA test items found")
    return items


def select_fixed_sample(
    items: list[PublicEvalItem],
    sample_size: int = DEFAULT_SAMPLE_SIZE,
    seed: int = DEFAULT_SAMPLE_SEED,
) -> list[PublicEvalItem]:
    """Return a deterministic sample without changing the source dataset."""

    if sample_size <= 0:
        raise ValueError("sample_size must be positive")
    if len(items) < sample_size:
        raise ValueError(f"Need at least {sample_size} items, found {len(items)}")

    ordered = sorted(items, key=lambda item: item.question_id)
    indices = random.Random(seed).sample(range(len(ordered)), sample_size)
    return [ordered[index] for index in sorted(indices)]
