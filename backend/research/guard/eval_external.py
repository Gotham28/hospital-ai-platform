"""Pure external benchmark adapters; no application imports or model changes."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict

LABELS = ("supported", "unsupported", "contradicted")
NLI_LABELS = {"entailment": "supported", "neutral": "unsupported", "contradiction": "contradicted"}
ERRORS = {"unsupported", "contradicted"}


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def align_nli(english: list[dict], malayalam: dict, *, expected: int = 5010) -> list[dict]:
    """Use documented upstream preserved order, checking every label and source ID.

    IndicXNLI exports no original IDs. This join is only justified together with
    the pinned upstream generation code and original XNLI loader in the manifest.
    """
    if set(malayalam) != {"test"} or len(english) != expected or len(malayalam["test"]) != expected:
        raise ValueError("Expected complete official test splits only")
    seen = set()
    items = []
    for ordinal, (en, ml) in enumerate(zip(english, malayalam["test"])):
        identifier = str(en["pairID"])
        if identifier in seen:
            raise ValueError("Duplicate original XNLI pairID")
        seen.add(identifier)
        gold = NLI_LABELS[en["gold_label"]]
        label = ml["label"]
        if type(label) is not int or label not in range(3) or LABELS[label] != gold:
            raise ValueError(f"EN/ML ordinal label mismatch at {ordinal}")
        texts = [en["sentence1"], en["sentence2"], ml["premise"], ml["hypothesis"]]
        if not all(isinstance(t, str) and t.strip() for t in texts):
            raise ValueError("Empty or invalid NLI text")
        items.append(dict(id=identifier, ordinal=ordinal, group=digest(en["sentence1"]),
                          en_premise=en["sentence1"], en_answer=en["sentence2"],
                          ml_premise=ml["premise"], ml_answer=ml["hypothesis"], gold=gold))
    return items


def adapt_ragtruth(response: dict, source: dict, *, required_split: str = "test") -> dict:
    if required_split not in {"train", "test"} or response["split"] != required_split or response["source_id"] != source["source_id"]:
        raise ValueError("RAGTruth requires the declared official split and an exact source join")
    answer, info, task, prompt = response["response"], source["source_info"], source["task_type"], source["prompt"]
    if task == "QA":
        body = info["passages"]
        # Preserve the published field intact; do not add retrieval/chunking.
        context = [body]
    elif task == "Summary":
        body, context = info, [info]
    elif task == "Data2txt":
        body, context = str(info), [str(info)]
    else:
        raise ValueError(f"Unknown task type: {task}")
    if prompt.count(body) != 1:
        raise ValueError(f"Cannot locate exact evidence in original {task} prompt")
    instructions = prompt.replace(body, "[EVIDENCE PROVIDED SEPARATELY]", 1)
    if not answer or not context or not all(isinstance(p, str) and p.strip() for p in context):
        raise ValueError("Invalid empty RAGTruth input")
    spans = []
    for label in response["labels"]:
        start, end = label["start"], label["end"]
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(answer) or answer[start:end] != label["text"]:
            raise ValueError(f"Invalid gold character span in response {response['id']}")
        spans.append([start, end])
    return dict(id=str(response["id"]), group=str(source["source_id"]), task=task, lang="en",
                answer=answer, context=context, instructions=instructions, gold_spans=spans,
                annotations=response["labels"], quality=response["quality"], model=response["model"] if "model" in response else "unknown")


def whole_verdict(claims: list[dict]) -> str:
    verdicts = {c["verdict"] for c in claims}
    if not verdicts:
        return "unmatched"
    for label in ("contradicted", "unsupported", "supported"):
        if label in verdicts:
            return label
    raise ValueError("Unknown guard verdict")


def removal_mask(answer: str, result: dict) -> set[int]:
    """Replay exact str.replace behavior with original-character attribution."""
    text = answer
    indices = list(range(len(answer)))
    removed = set()
    for claim in result["claims"]:
        if not claim.get("altered", claim["verdict"] in ERRORS):
            continue
        target = claim["text"]
        if not target:
            raise ValueError("Empty predicted error fragment")
        cursor = 0
        while (start := text.find(target, cursor)) >= 0:
            end = start + len(target)
            removed.update(i for i in indices[start:end] if i is not None)
            text = text[:start] + "[FLAG_TEXT]" + text[end:]
            indices[start:end] = [None] * len("[FLAG_TEXT]")
            cursor = start + len("[FLAG_TEXT]")
    if text != result["final_answer"]:
        raise ValueError("Guard redaction replay differs from final_answer")
    return removed


def score_spans(answer: str, spans: list[list[int]], removed: set[int]) -> dict:
    # Match the published character-overlap definition, including whitespace.
    gold = {i for start, end in spans for i in range(start, end)}
    predicted = set(removed)
    return dict(tp_chars=len(gold & predicted), fp_chars=len(predicted - gold), fn_chars=len(gold - predicted),
                fully_intercepted=gold <= predicted if gold else None,
                annotated_spans=len(spans), intercepted_spans=sum(
                    set(range(start, end)) <= predicted for start, end in spans))


def ratio(n: float, d: float) -> float | None:
    return n / d if d else None


def binary_summary(actual: list[bool], predicted: list[bool]) -> dict:
    if len(actual) != len(predicted):
        raise ValueError("Mismatched binary rows")
    tp = sum(a and p for a, p in zip(actual, predicted))
    fp = sum(not a and p for a, p in zip(actual, predicted))
    fn = sum(a and not p for a, p in zip(actual, predicted))
    tn = sum(not a and not p for a, p in zip(actual, predicted))
    return dict(n=len(actual), tp=tp, fp=fp, fn=fn, tn=tn, precision=ratio(tp, tp + fp),
                recall=ratio(tp, tp + fn), f1=ratio(2 * tp, 2 * tp + fp + fn), accuracy=ratio(tp + tn, len(actual)))


def check_resume(identity: dict, previous: dict, records: list[dict], expected: set[str]) -> None:
    if identity != previous:
        raise ValueError("Resume rejected: code/data/models/thresholds/options drift")
    keys = [r["key"] for r in records]
    if len(keys) != len(set(keys)) or not set(keys) <= expected:
        raise ValueError("Resume rejected: duplicate or unexpected keys")


def classification(actual: list[str], predicted: list[str]) -> dict:
    matrix = {g: {p: 0 for p in (*LABELS, "unmatched")} for g in LABELS}
    for gold, pred in zip(actual, predicted):
        matrix[gold][pred] += 1
    per_class = {}
    for label in LABELS:
        tp = matrix[label][label]
        fp = sum(matrix[g][label] for g in LABELS if g != label)
        fn = sum(v for p, v in matrix[label].items() if p != label)
        per_class[label] = dict(precision=ratio(tp, tp + fp), recall=ratio(tp, tp + fn),
                                f1=ratio(2 * tp, 2 * tp + fp + fn))
    return dict(n=len(actual), confusion_matrix=matrix, per_class=per_class,
                accuracy=ratio(sum(a == p for a, p in zip(actual, predicted)), len(actual)),
                macro_f1=sum(c["f1"] or 0 for c in per_class.values()) / 3)


def summarize_group(rows: list[dict]) -> dict:
    import numpy as np
    good = [r for r in rows if "error" not in r]
    gold = [r["gold_error"] for r in good]
    predicted = [r["predicted_error"] for r in good]
    supported = [r for r in good if not r["gold_error"]]
    erroneous = [r for r in good if r["gold_error"]]
    timings = [r["elapsed_seconds"] for r in good]
    alters = any("changed" in r for r in good)
    result = dict(selected=len(rows), completed=len(good), failures=len(rows) - len(good),
                  unique_source_groups=len({r["group"] for r in rows}), detection=binary_summary(gold, predicted),
                  supported_answers=len(supported), false_alterations=sum(r.get("changed", False) for r in supported) if alters else None,
                  false_alteration_rate=ratio(sum(r.get("changed", False) for r in supported), len(supported)) if alters else None,
                  latency=dict(n=len(timings), mean=float(np.mean(timings)) if timings else None,
                               p50=float(np.percentile(timings, 50)) if timings else None,
                               p95=float(np.percentile(timings, 95)) if timings else None),
                  truncation_pairs=sum(r.get("truncation", {}).get("pairs", 0) for r in good),
                  truncated_pairs=sum(r.get("truncation", {}).get("truncated", 0) for r in good))
    if good and "gold" in good[0]:
        result["classification"] = classification([r["gold"] for r in good], [r["predicted"] for r in good])
    if any("spans" in r for r in erroneous):
        spans = [r["spans"] for r in good]
        tp, fp, fn = [sum(s[k] for s in spans) for k in ("tp_chars", "fp_chars", "fn_chars")]
        fully = sum(bool(r["spans"]["fully_intercepted"]) for r in erroneous)
        result["redaction"] = dict(erroneous_answers=len(erroneous), fully_intercepted=fully,
                                   residual_error_answers=len(erroneous) - fully,
                                   character_precision=ratio(tp, tp + fp), character_recall=ratio(tp, tp + fn),
                                   character_f1=ratio(2 * tp, 2 * tp + fp + fn), tp_chars=tp, fp_chars=fp, fn_chars=fn,
                                   annotated_spans=sum(s["annotated_spans"] for s in spans),
                                   intercepted_spans=sum(s["intercepted_spans"] for s in spans))
    return result


def cluster_intervals(rows: list[dict], *, samples: int = 2000, seed: int = 20261026) -> dict:
    """Percentile bootstrap; source group is the unit, never language variant."""
    import numpy as np
    groups = defaultdict(list)
    for row in rows:
        if "error" not in row:
            groups[row["group"]].append(row)
    if not groups:
        return {}
    vectors = []
    for group in groups.values():
        tp = sum(r["gold_error"] and r["predicted_error"] for r in group)
        fp = sum(not r["gold_error"] and r["predicted_error"] for r in group)
        fn = sum(r["gold_error"] and not r["predicted_error"] for r in group)
        tn = len(group) - tp - fp - fn
        vectors.append([tp, fp, fn, tn, sum(r.get("changed", False) and not r["gold_error"] for r in group)])
    data = np.asarray(vectors, dtype=float)
    rng = np.random.default_rng(seed)
    totals = np.array([data[rng.integers(len(data), size=len(data))].sum(axis=0) for _ in range(samples)])
    tp, fp, fn, tn, changed = totals.T
    def interval(num, den):
        values = np.divide(num, den, out=np.full_like(num, np.nan), where=den != 0)
        return [float(x) for x in np.nanpercentile(values, [2.5, 97.5])] if np.isfinite(values).any() else None
    return dict(method="source-cluster percentile bootstrap", samples=samples, seed=seed, groups=len(data),
                precision=interval(tp, tp + fp), recall=interval(tp, tp + fn),
                f1=interval(2 * tp, 2 * tp + fp + fn), accuracy=interval(tp + tn, tp + fp + fn + tn),
                false_alteration_rate=interval(changed, fp + tn) if any("changed" in r for r in rows) else None)


def paired_gap_intervals(english: list[dict], malayalam: list[dict], *, samples: int = 2000) -> dict:
    """Resample the same source groups for both translated-language conditions."""
    import numpy as np
    en, ml = ({r["id"]: r for r in rows if "error" not in r} for rows in (english, malayalam))
    if en.keys() != ml.keys():
        return dict(unavailable="Different completed EN/ML pair IDs")
    grouped = defaultdict(list)
    for key in en:
        if en[key]["group"] != ml[key]["group"] or en[key]["gold"] != ml[key]["gold"]:
            raise ValueError("Paired bootstrap group/gold mismatch")
        grouped[en[key]["group"]].append(key)
    if not grouped:
        return {}
    vectors = []
    for identifiers in grouped.values():
        vector = []
        for language in (en, ml):
            rows = [language[k] for k in identifiers]
            vector += [sum(r["gold_error"] and r["predicted_error"] for r in rows),
                       sum(not r["gold_error"] and r["predicted_error"] for r in rows),
                       sum(r["gold_error"] and not r["predicted_error"] for r in rows),
                       sum(not r["gold_error"] and not r["predicted_error"] for r in rows),
                       sum(r["gold"] == r["predicted"] for r in rows), len(rows)]
        vectors.append(vector)
    data = np.asarray(vectors, dtype=float)
    rng = np.random.default_rng(20261026)
    totals = np.array([data[rng.integers(len(data), size=len(data))].sum(axis=0) for _ in range(samples)])
    def metrics(values):
        tp, fp, fn, tn, correct, n = values.T
        def divide(num, den):
            return np.divide(num, den, out=np.full_like(num, np.nan), where=den != 0)
        return dict(precision=divide(tp, tp + fp), recall=divide(tp, tp + fn),
                    f1=divide(2 * tp, 2 * tp + fp + fn), accuracy=divide(tp + tn, n),
                    three_class_accuracy=divide(correct, n))
    a, b = metrics(totals[:, :6]), metrics(totals[:, 6:])
    intervals = {k: [float(v) for v in np.nanpercentile(a[k] - b[k], [2.5, 97.5])]
                 if np.isfinite(a[k] - b[k]).any() else None for k in a}
    return dict(method="paired source-cluster percentile bootstrap", samples=samples, groups=len(data),
                seed=20261026, ci95=intervals)


def language_gaps(english: list[dict], malayalam: list[dict]) -> dict:
    en = [r for r in english if "error" not in r]
    ml = [r for r in malayalam if "error" not in r]
    if not en or {r["id"] for r in en} != {r["id"] for r in ml}:
        return dict(unavailable="Incomplete or unequal completed bilingual pair IDs", en_completed=len(en), ml_completed=len(ml))
    a, b = summarize_group(en), summarize_group(ml)
    result = {metric: a["detection"][metric] - b["detection"][metric]
              if a["detection"][metric] is not None and b["detection"][metric] is not None else None
              for metric in ("precision", "recall", "f1", "accuracy")}
    result.update(three_class_accuracy=a["classification"]["accuracy"] - b["classification"]["accuracy"],
                  macro_f1=a["classification"]["macro_f1"] - b["classification"]["macro_f1"],
                  completed_pairs=len(en), paired_ci95=paired_gap_intervals(en, ml))
    return result
