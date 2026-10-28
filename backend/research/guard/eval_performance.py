"""Offline measurement helpers; never change guard decisions or gold labels."""

from __future__ import annotations

import statistics
from typing import Any

LABELS = ("supported", "unsupported", "contradicted")
ERRORS = {"unsupported", "contradicted"}


def divide(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def binary_metrics(actual: list[bool], predicted: list[bool]) -> dict[str, Any]:
    if len(actual) != len(predicted):
        raise ValueError("actual/predicted lengths differ")
    tp = sum(a and p for a, p in zip(actual, predicted))
    fp = sum(not a and p for a, p in zip(actual, predicted))
    fn = sum(a and not p for a, p in zip(actual, predicted))
    tn = sum(not a and not p for a, p in zip(actual, predicted))
    return dict(n=len(actual), tp=tp, fp=fp, fn=fn, tn=tn,
                precision=divide(tp, tp + fp), recall=divide(tp, tp + fn),
                f1=divide(2 * tp, 2 * tp + fp + fn),
                accuracy=divide(tp + tn, len(actual)))


def _spans(answer: str, texts: list[str]) -> list[tuple[int, int] | None]:
    cursor = 0
    spans = []
    for text in texts:
        start = answer.find(text, cursor) if text else -1
        spans.append((start, start + len(text)) if start >= 0 else None)
        if start >= 0:
            cursor = start + len(text)
    return spans


def align_claims(item: dict, result: dict) -> list[dict]:
    """Map original text spans, allowing complete contiguous fragment groups.

    A fragment spanning two gold claims is ambiguous. Punctuation/whitespace gaps
    are allowed; missing letters/digits are not. Any contradicted fragment makes
    its complete group contradicted, then unsupported, then supported. Missing or
    ambiguous extraction is an explicit unmatched prediction, never dropped.
    """
    answer = item["answer"]
    gold = item["ground_truth"]["claims"]
    predictions = result["claims"]
    gold_spans = _spans(answer, [c["text"] for c in gold])
    pred_spans = _spans(answer, [c["text"] for c in predictions])
    rows = []
    for claim, span in zip(gold, gold_spans):
        indices = []
        covered: set[int] = set()
        ambiguous = False
        if span is not None:
            start, end = span
            for index, pred_span in enumerate(pred_spans):
                if pred_span is None:
                    continue
                left, right = pred_span
                if left < end and right > start:
                    if left < start or right > end:
                        ambiguous = True
                    else:
                        indices.append(index)
                        covered.update(range(left, right))
            complete = bool(indices) and not ambiguous and all(
                index in covered or not answer[index].isalnum()
                for index in range(start, end)
            )
        else:
            complete = False
        verdicts = [predictions[i]["verdict"] for i in indices]
        if not complete:
            predicted = "unmatched"
        elif "contradicted" in verdicts:
            predicted = "contradicted"
        elif "unsupported" in verdicts:
            predicted = "unsupported"
        else:
            predicted = "supported"
        rows.append(dict(text=claim["text"], gold=claim["verdict"],
                         predicted=predicted, prediction_indices=indices,
                         fragments=len(indices), complete=complete,
                         ambiguous=ambiguous))
    return rows


def interception(item: dict, result: dict) -> dict:
    """Prove full gold-error-span redaction using original character origins.

    Replay the guard's declared replacements, verify the resulting string equals
    its returned final answer, and check whether any original alphanumeric from
    an erroneous gold claim survives. Partial removal never counts as complete
    interception. This measures removal, not factual correction or readability.
    """
    original = item["answer"]
    current = original
    origins: list[int | None] = list(range(len(original)))
    for claim in result["claims"]:
        text = claim["text"]
        if claim["verdict"] not in ERRORS or not text:
            continue
        cursor = 0
        while (index := current.find(text, cursor)) >= 0:
            current = current[:index] + "[FLAG_TEXT]" + current[index + len(text):]
            origins[index:index + len(text)] = [None] * len("[FLAG_TEXT]")
            cursor = index + len("[FLAG_TEXT]")
    proven = current == result["final_answer"]
    remaining = {i for i in origins if i is not None and original[i].isalnum()}
    claims = item["ground_truth"]["claims"]
    spans = _spans(original, [c["text"] for c in claims])
    bad = [(c, s) for c, s in zip(claims, spans) if c["verdict"] in ERRORS]
    residual = sum(
        not proven or span is None or any(i in remaining for i in range(*span))
        for _, span in bad
    )
    erroneous = item["ground_truth"]["overall_verdict"] in ERRORS
    return dict(replacement_replay_verified=proven, erroneous_gold_claims=len(bad),
                residual_erroneous_claims=residual,
                fully_intercepted=bool(erroneous and bad and proven and residual == 0))


def claim_metrics(rows: list[dict]) -> dict:
    matrix = {label: {p: 0 for p in (*LABELS, "unmatched")} for label in LABELS}
    for row in rows:
        matrix[row["gold"]][row["predicted"]] += 1
    per_class = {}
    for label in LABELS:
        tp = matrix[label][label]
        fp = sum(matrix[other][label] for other in LABELS if other != label)
        fn = sum(matrix[label][p] for p in (*LABELS, "unmatched") if p != label)
        per_class[label] = dict(support=sum(matrix[label].values()), tp=tp, fp=fp, fn=fn,
                               precision=divide(tp, tp + fp), recall=divide(tp, tp + fn),
                               f1=divide(2 * tp, 2 * tp + fp + fn))
    f1s = [entry["f1"] for entry in per_class.values()]
    return dict(n=len(rows), confusion_matrix=matrix, per_class=per_class,
                accuracy=divide(sum(matrix[x][x] for x in LABELS), len(rows)),
                macro_f1=sum(f1s) / len(f1s) if all(x is not None for x in f1s) else None,
                extraction_complete=sum(row["complete"] for row in rows),
                fragmented_gold_claims=sum(row["fragments"] > 1 for row in rows),
                unmatched=sum(row["predicted"] == "unmatched" for row in rows))


def latency(values: list[float]) -> dict:
    ordered = sorted(values)
    # Linear interpolation, explicitly reproducible for small samples.
    def percentile(q: float) -> float | None:
        if not ordered:
            return None
        position = (len(ordered) - 1) * q
        left = int(position)
        right = min(left + 1, len(ordered) - 1)
        return ordered[left] + (ordered[right] - ordered[left]) * (position - left)
    return dict(n=len(values), mean_seconds=statistics.mean(values) if values else None,
                p50_seconds=percentile(.50), p95_seconds=percentile(.95))


def summarize(records: list[dict]) -> dict:
    groups = {}
    for split in ("all", "tuning", "holdout"):
        for lang in ("all", "en", "ml"):
            selected = [r for r in records if (split == "all" or r["split"] == split)
                        and (lang == "all" or r["lang"] == lang)]
            gold = [r["gold_overall"] in ERRORS for r in selected]
            detected = [any(c["verdict"] in ERRORS for c in r["result"]["claims"])
                        for r in selected]
            supported = [r for r in selected if r["gold_overall"] == "supported"]
            changed_supported = sum(r["result"]["changed"] for r in supported)
            claim_rows = [row for r in selected for row in r["alignment"]]
            groups[f"{split}/{lang}"] = dict(
                answers=len(selected), claims=claim_metrics(claim_rows),
                answer_error_detection=binary_metrics(gold, detected),
                altered_answers=sum(r["result"]["changed"] for r in selected),
                supported_answers=len(supported), false_alterations=changed_supported,
                false_alteration_rate=divide(changed_supported, len(supported)),
                erroneous_answers=sum(gold),
                fully_intercepted_answers=sum(r["interception"]["fully_intercepted"] for r in selected),
                residual_erroneous_answers=sum(
                    r["gold_overall"] in ERRORS and not r["interception"]["fully_intercepted"]
                    for r in selected),
                residual_erroneous_claims=sum(r["interception"]["residual_erroneous_claims"] for r in selected),
                gold_final_answer_exact_matches=sum(r["gold_final_answer_exact_match"] for r in selected),
                latency=latency([r["elapsed_seconds"] for r in selected]),
            )
    gaps = {}
    for split in ("all", "tuning", "holdout"):
        en, ml = groups[f"{split}/en"], groups[f"{split}/ml"]
        pairs = dict(claim_accuracy=(en["claims"]["accuracy"], ml["claims"]["accuracy"]),
                     claim_macro_f1=(en["claims"]["macro_f1"], ml["claims"]["macro_f1"]),
                     detection_f1=(en["answer_error_detection"]["f1"], ml["answer_error_detection"]["f1"]),
                     false_alteration_rate=(en["false_alteration_rate"], ml["false_alteration_rate"]))
        for metric in ("precision", "recall", "accuracy"):
            pairs[f"detection_{metric}"] = (en["answer_error_detection"][metric], ml["answer_error_detection"][metric])
        for label in LABELS:
            for metric in ("precision", "recall", "f1"):
                pairs[f"claim_{label}_{metric}"] = (en["claims"]["per_class"][label][metric],
                                                    ml["claims"]["per_class"][label][metric])
        for metric in ("mean_seconds", "p50_seconds", "p95_seconds"):
            pairs[f"latency_{metric}"] = (en["latency"][metric], ml["latency"][metric])
        gaps[split] = {name: a - b if a is not None and b is not None else None
                       for name, (a, b) in pairs.items()}
    return dict(groups=groups, en_minus_ml=gaps)
