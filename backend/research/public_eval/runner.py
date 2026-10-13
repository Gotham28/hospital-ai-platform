"""Plain public-evaluation runner with dry-run and resume support."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .loader import (
    DEFAULT_SAMPLE_SEED,
    DEFAULT_SAMPLE_SIZE,
    PublicEvalItem,
    load_ragtruth_qa_test_items,
    select_fixed_sample,
)


@dataclass(frozen=True)
class GeneratedAnswer:
    """A model result recorded without retaining provider-specific objects."""

    text: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0


@dataclass(frozen=True)
class RunConfig:
    """Fields shared with the Track 1 result-row contract."""

    run_id: str
    model: str
    model_version: str
    temperature: float = 0.0
    translator: str = "none"
    prompt_snapshot_commit: str = "uncommitted"
    data_condition: str = "correct_data"
    instruction_condition: str = "dataset_prompt"
    ml_strategy: str = "not_applicable"
    estimated_cost_per_call_usd: float = 0.0


AnswerGenerator = Callable[[PublicEvalItem], GeneratedAnswer]


def _load_completed_ids(output_path: Path) -> set[str]:
    if not output_path.exists():
        return set()

    completed: set[str] = set()
    with output_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL in {output_path} at line {line_number}") from exc
            question_id = row.get("question_id")
            if not isinstance(question_id, str):
                raise ValueError(f"Missing question_id in {output_path} at line {line_number}")
            completed.add(question_id)
    return completed


def dry_run(items: list[PublicEvalItem], output_path: Path, config: RunConfig) -> dict[str, Any]:
    """Preview remaining calls and estimated cost without invoking a model."""

    completed = _load_completed_ids(output_path)
    remaining = [item for item in items if item.question_id not in completed]
    return {
        "dataset_items": len(items),
        "completed": len(items) - len(remaining),
        "remaining_calls": len(remaining),
        "estimated_cost_usd": round(len(remaining) * config.estimated_cost_per_call_usd, 6),
        "model": config.model,
        "output_path": str(output_path),
    }


def _result_row(item: PublicEvalItem, answer: GeneratedAnswer, config: RunConfig) -> dict[str, Any]:
    return {
        "run_id": config.run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "part": "D",
        "question_id": item.question_id,
        "lang": "en",
        "mode": "lab",
        "data_condition": config.data_condition,
        "instruction_condition": config.instruction_condition,
        "ml_strategy": config.ml_strategy,
        "model": config.model,
        "model_version": config.model_version,
        "translator": config.translator,
        "temperature": config.temperature,
        "prompt_snapshot_commit": config.prompt_snapshot_commit,
        "guard": "off",
        "repeat_index": 0,
        "answer_text": answer.text,
        "score_label": None,
        "tokens_in": answer.tokens_in,
        "tokens_out": answer.tokens_out,
        "cost_usd": answer.cost_usd,
    }


def run_evaluation(
    items: list[PublicEvalItem],
    generate_answer: AnswerGenerator,
    output_path: Path,
    config: RunConfig,
) -> dict[str, int]:
    """Generate answers and append rows, skipping completed items on restart."""

    completed = _load_completed_ids(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    skipped = 0
    with output_path.open("a", encoding="utf-8") as handle:
        for item in items:
            if item.question_id in completed:
                skipped += 1
                continue
            answer = generate_answer(item)
            if not isinstance(answer, GeneratedAnswer):
                raise TypeError("generate_answer must return GeneratedAnswer")
            handle.write(json.dumps(_result_row(item, answer, config), ensure_ascii=False) + "\n")
            handle.flush()
            written += 1
    return {"written": written, "skipped": skipped}


def format_dry_run(summary: dict[str, Any]) -> str:
    """Render a human-readable dry-run preview."""

    return "\n".join(
        [
            "=== PUBLIC EVALUATION DRY RUN ===",
            f"Dataset items: {summary['dataset_items']}",
            f"Completed already: {summary['completed']}",
            f"Model calls remaining: {summary['remaining_calls']}",
            f"Estimated cost (USD): {summary['estimated_cost_usd']:.6f}",
            f"Model: {summary['model']}",
            f"Output: {summary['output_path']}",
        ]
    )


def main() -> None:
    """Run a no-cost preflight for a locally downloaded RAGTruth dataset."""

    parser = argparse.ArgumentParser(description="Preview a RAGTruth public-evaluation run")
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-version", default="unspecified")
    parser.add_argument("--seed", type=int, default=DEFAULT_SAMPLE_SEED)
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE)
    parser.add_argument("--estimated-cost-per-call-usd", type=float, default=0.0)
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()

    if not arguments.dry_run:
        parser.error(
            "This G-04 runner only exposes dry-run on the command line. "
            "Pass a reviewed model adapter to run_evaluation() for an actual model run."
        )

    items = select_fixed_sample(
        load_ragtruth_qa_test_items(arguments.dataset_dir),
        sample_size=arguments.sample_size,
        seed=arguments.seed,
    )
    config = RunConfig(
        run_id="dry-run",
        model=arguments.model,
        model_version=arguments.model_version,
        estimated_cost_per_call_usd=arguments.estimated_cost_per_call_usd,
    )
    print(format_dry_run(dry_run(items, arguments.output, config)))


if __name__ == "__main__":
    main()
