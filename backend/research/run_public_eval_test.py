"""Offline checks for the G-04 RAGTruth loader and plain runner."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile

from backend.research.public_eval.loader import (
    DEFAULT_SAMPLE_SEED,
    load_ragtruth_qa_test_items,
    select_fixed_sample,
)
from backend.research.public_eval.runner import (
    GeneratedAnswer,
    RunConfig,
    dry_run,
    format_dry_run,
    run_evaluation,
)


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")


def _make_dataset(dataset_dir: Path) -> None:
    sources = []
    responses = []
    for index in range(301):
        source_id = str(index)
        sources.append(
            {
                "source_id": source_id,
                "task_type": "QA",
                "source_info": {
                    "question": f"Synthetic question {index}?",
                    "passages": f"passage 1: Synthetic fact {index}.",
                },
                "prompt": f"Answer synthetic question {index} using the passage.",
            }
        )
        responses.append({"source_id": source_id, "split": "test", "quality": "good"})
    _write_jsonl(dataset_dir / "source_info.jsonl", sources)
    _write_jsonl(dataset_dir / "response.jsonl", responses)


def main() -> None:
    temporary_parent = Path("backend/research/results")
    temporary_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temporary_parent) as temporary_directory:
        root = Path(temporary_directory)
        dataset_dir = root / "dataset"
        dataset_dir.mkdir()
        _make_dataset(dataset_dir)

        items = load_ragtruth_qa_test_items(dataset_dir)
        sample = select_fixed_sample(items)
        same_sample = select_fixed_sample(items, seed=DEFAULT_SAMPLE_SEED)
        assert len(items) == 301
        assert len(sample) == 300
        assert [item.question_id for item in sample] == [item.question_id for item in same_sample]
        assert all(item.context[0].startswith("passage 1:") for item in sample)

        output_path = root / "results" / "public_eval.jsonl"
        config = RunConfig(
            run_id="test-run",
            model="pretend-model",
            model_version="test",
            estimated_cost_per_call_usd=0.002,
        )
        preview = dry_run(sample, output_path, config)
        assert preview["remaining_calls"] == 300
        assert preview["estimated_cost_usd"] == 0.6

        calls: list[str] = []

        def pretend_model(item):
            calls.append(item.question_id)
            return GeneratedAnswer(text=f"Answer for {item.question_id}", tokens_in=3, tokens_out=4)

        first_run = run_evaluation(sample[:2], pretend_model, output_path, config)
        second_run = run_evaluation(sample[:2], pretend_model, output_path, config)
        assert first_run == {"written": 2, "skipped": 0}
        assert second_run == {"written": 0, "skipped": 2}
        assert len(calls) == 2

        rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
        assert len(rows) == 2
        assert set(rows[0]) == {
            "run_id", "timestamp_utc", "part", "question_id", "lang", "mode",
            "data_condition", "instruction_condition", "ml_strategy", "model",
            "model_version", "translator", "temperature", "prompt_snapshot_commit",
            "guard", "repeat_index", "answer_text", "score_label", "tokens_in",
            "tokens_out", "cost_usd",
        }
        assert rows[0]["guard"] == "off"
        assert rows[0]["part"] == "D"

    print("PASS loader reads usable RAGTruth QA test records")
    print("PASS fixed 300-item sample is deterministic")
    print(format_dry_run(preview))
    print("PASS dry-run reports calls and estimated cost without model calls")
    print("PASS runner writes shared-contract rows and resumes safely")
    print("4 passed, 0 failed")


if __name__ == "__main__":
    main()
