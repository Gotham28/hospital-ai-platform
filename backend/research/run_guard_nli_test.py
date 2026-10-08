"""Tune NLI thresholds on the tuning split and report once on holdout."""

from __future__ import annotations

import json
import os
from pathlib import Path
import time

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from backend.research.guard.nli import MODEL_CACHE, MODEL_ID, MultilingualNLIScorer

ROOT = Path(__file__).parent
FIXTURE = ROOT / "fixtures" / "guard_dev_set.json"
THRESHOLDS_PATH = ROOT / "guard" / "thresholds.json"
REPORT_PATH = ROOT / "notes" / "nli_report.md"
TRANSLATION_MODEL_ID = "Helsinki-NLP/opus-mt-ml-en"
LABELS = ("supported", "unsupported", "contradicted")
GRID = tuple(round(value / 100, 2) for value in range(30, 91, 5))


class MalayalamToEnglish:
    def __init__(self, device: str = "cpu") -> None:
        self.tokenizer = AutoTokenizer.from_pretrained(
            TRANSLATION_MODEL_ID, cache_dir=MODEL_CACHE
        )
        self.model = AutoModelForSeq2SeqLM.from_pretrained(
            TRANSLATION_MODEL_ID, cache_dir=MODEL_CACHE
        )
        self.device = torch.device(device)
        self.model.to(self.device)
        self.model.eval()

    def translate(self, text: str) -> str:
        encoded = self.tokenizer(
            text, return_tensors="pt", truncation=True, max_length=512
        )
        encoded = {key: value.to(self.device) for key, value in encoded.items()}
        with torch.inference_mode():
            generated = self.model.generate(**encoded, max_new_tokens=128)
        return self.tokenizer.decode(generated[0], skip_special_tokens=True)


def _prediction(row: dict, entailment_threshold: float, contradiction_threshold: float) -> str:
    if row["exact_verdict"] is not None:
        return row["exact_verdict"]
    scores = row["scores"]
    if (
        scores["contradiction"] >= contradiction_threshold
        and scores["contradiction"] > scores["entailment"]
    ):
        return "contradicted"
    if scores["entailment"] >= entailment_threshold:
        return "supported"
    return "unsupported"


def _macro_f1(rows: list[dict], entailment_threshold: float, contradiction_threshold: float) -> float:
    values = []
    for label in LABELS:
        tp = sum(
            row["gold"] == label
            and _prediction(row, entailment_threshold, contradiction_threshold) == label
            for row in rows
        )
        fp = sum(
            row["gold"] != label
            and _prediction(row, entailment_threshold, contradiction_threshold) == label
            for row in rows
        )
        fn = sum(
            row["gold"] == label
            and _prediction(row, entailment_threshold, contradiction_threshold) != label
            for row in rows
        )
        denom = 2 * tp + fp + fn
        values.append((2 * tp / denom) if denom else 0.0)
    return sum(values) / len(values)


def _tune(rows: list[dict]) -> dict[str, float]:
    if not rows:
        raise ValueError("No tuning rows available")
    best: tuple[float, float, float] | None = None
    for entailment in GRID:
        for contradiction in GRID:
            score = _macro_f1(rows, entailment, contradiction)
            candidate = (score, entailment, contradiction)
            if best is None or candidate > best:
                best = candidate
    assert best is not None
    return {"entailment": best[1], "contradiction": best[2], "macro_f1_tuning": best[0]}


def _class_metrics(rows: list[dict], label: str, ent: float, con: float) -> tuple[float, float]:
    tp = sum(
        row["gold"] == label and _prediction(row, ent, con) == label for row in rows
    )
    fp = sum(
        row["gold"] != label and _prediction(row, ent, con) == label for row in rows
    )
    fn = sum(
        row["gold"] == label and _prediction(row, ent, con) != label for row in rows
    )
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return precision, recall


def _collect_rows(
    items: list[dict],
    scorer: MultilingualNLIScorer,
    translator: MalayalamToEnglish,
    option: str,
) -> list[dict]:
    rows: list[dict] = []
    for item in items:
        for claim in item["ground_truth"]["claims"]:
            hypothesis = claim["text"]
            if option == "pivot" and item["lang"] == "ml":
                hypothesis = translator.translate(hypothesis)
            assessment = scorer.assess(
                hypothesis,
                item["context"],
                entailment_threshold=0.5,
                contradiction_threshold=0.5,
            )
            rows.append(
                {
                    "id": item["id"],
                    "split": item["split"],
                    "lang": item["lang"],
                    "gold": claim["verdict"],
                    "scores": {
                        "entailment": assessment.scores.entailment,
                        "neutral": assessment.scores.neutral,
                        "contradiction": assessment.scores.contradiction,
                    },
                    "exact_verdict": assessment.exact_verdict,
                }
            )
    return rows


def _render_report(results: dict, device: str, elapsed_seconds: float) -> str:
    lines = [
        "# G-08 NLI evaluation",
        "",
        f"Model: [{MODEL_ID}](https://huggingface.co/{MODEL_ID})",
        f"Malayalam-to-English pivot: [{TRANSLATION_MODEL_ID}](https://huggingface.co/{TRANSLATION_MODEL_ID})",
        f"Device: {device}",
        "Thresholds were selected using tuning rows only; holdout labels were not used for tuning.",
        "The pivot option translates Malayalam claims to English; context passages remain unchanged.",
        "Exact-value overrides use nearby price, time, and duration keywords and may miss entity attribution.",
        "",
        f"Evaluation elapsed seconds: {elapsed_seconds:.2f}",
        "",
        "| Option | Language | Entailment threshold | Contradiction threshold | Class | Precision | Recall |",
        "|---|---|---:|---:|---|---:|---:|",
    ]
    for option, by_language in results.items():
        for lang, values in by_language.items():
            for label in ("unsupported", "contradicted"):
                precision, recall = values["metrics"][label]
                lines.append(
                    f"| {option} | {lang} | {values['thresholds']['entailment']:.2f} "
                    f"| {values['thresholds']['contradiction']:.2f} | {label} "
                    f"| {precision:.3f} | {recall:.3f} |"
                )
    lines.extend(
        [
            "",
            "The holdout report is a single evaluation. Do not adjust thresholds from these results.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    started = time.perf_counter()
    items = json.loads(FIXTURE.read_text(encoding="utf-8"))
    # The local RTX 3050 produced a CUDA matmul error for this model; CPU inference
    # keeps the experiment reproducible on the current machine.
    device = "cpu"
    scorer = MultilingualNLIScorer(device=device)
    translator = MalayalamToEnglish(device=device)
    collected = {
        option: _collect_rows(items, scorer, translator, option)
        for option in ("direct", "pivot")
    }
    thresholds: dict[str, dict[str, dict[str, float]]] = {}
    results: dict[str, dict[str, dict]] = {}
    for option, rows in collected.items():
        thresholds[option] = {}
        results[option] = {}
        for lang in ("en", "ml"):
            tuning = [row for row in rows if row["split"] == "tuning" and row["lang"] == lang]
            holdout = [row for row in rows if row["split"] == "holdout" and row["lang"] == lang]
            chosen = _tune(tuning)
            thresholds[option][lang] = chosen
            results[option][lang] = {
                "thresholds": chosen,
                "metrics": {
                    label: _class_metrics(
                        holdout,
                        label,
                        chosen["entailment"],
                        chosen["contradiction"],
                    )
                    for label in ("unsupported", "contradicted")
                },
            }

    THRESHOLDS_PATH.write_text(
        json.dumps(
            {
                "nli_model": MODEL_ID,
                "translation_model": TRANSLATION_MODEL_ID,
                "optimization": "macro_f1_on_tuning_split_only",
                "results": thresholds,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    elapsed = time.perf_counter() - started
    report = _render_report(results, device, elapsed)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(report)
    print(f"Thresholds saved: {THRESHOLDS_PATH.relative_to(ROOT)}")
    print(f"Report saved: {REPORT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
