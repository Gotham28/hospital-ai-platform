"""Baseline replay gate over 720 development answers in strict mode."""

from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(".").resolve()))

from backend.research.guard.action_policy import BASELINE, should_alter
from backend.research.guard.eval_external import removal_mask, score_spans
from backend.research.guard.guard import _thresholds
from backend.research.replay.cache import NLICache
from backend.research.replay.scorer import CachedScorer
from backend.research.run_guard_calibration import load_inputs, metrics, score_policy, selected_items

CACHE_PATH = Path("backend/research/results/guard-diagnosis-2026-10-28/nli_cache.jsonl")
TRACES_PATH = Path("backend/research/results/guard-parser-v5-2026-10-28/development-v5-traces.jsonl")
RAG_RESPONSE_PATH = Path("backend/research/results/guard-external-2026-10-26/data/rag-response.jsonl")


def run_baseline_replay_gate(
    cache_path: Path = CACHE_PATH,
    traces_path: Path = TRACES_PATH,
    rag_response_path: Path = RAG_RESPONSE_PATH,
) -> bool:
    print("=" * 70)
    print("RUNNING BASELINE REPLAY GATE (strict mode, no model load)")
    print("=" * 70)

    # 1. Load inputs and traces
    manifest, responses = load_inputs()
    dev_items = {item["id"]: item for item in selected_items(manifest, responses, "development")}
    stored_traces = [json.loads(line) for line in traces_path.read_text(encoding="utf-8").splitlines()]
    stored_by_id = {str(t["id"]): t for t in stored_traces}

    # 2. Load rag-response labels for label-type interception
    rag_labels_by_id: dict[str, list[dict]] = {}
    if rag_response_path.exists():
        with rag_response_path.open("r", encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                if r.get("labels"):
                    rag_labels_by_id[str(r["id"])] = r["labels"]

    # 3. Instantiate CachedScorer in strict mode
    cache = NLICache(cache_path)
    scorer = CachedScorer(cache, mode="strict")
    assert scorer._model is None, "Strict mode must NOT load model weights into memory!"
    print(f"Loaded NLICache with {len(cache)} entries. Scorer in strict mode.")

    _, thresholds = _thresholds("en")

    # 4. Replay claim assessments
    print("\nReplaying claim assessments across 720 development answers...")
    total_claims = 0
    verdict_mismatches = []
    exact_mismatches = []
    max_score_diff = 0.0

    replayed_traces: list[dict] = []

    for idx, (tid, item) in enumerate(dev_items.items(), 1):
        stored = stored_by_id[tid]
        answer = item["answer"]
        re_claims = []

        for c_idx, stored_c in enumerate(stored["claims"]):
            total_claims += 1
            claim_text = stored_c["text"]
            assessment = scorer.assess(
                claim_text,
                item["context"],
                entailment_threshold=thresholds.entailment,
                contradiction_threshold=thresholds.contradiction,
            )

            # Check verdict
            if assessment.verdict != stored_c["verdict"]:
                verdict_mismatches.append({
                    "answer_id": tid,
                    "claim_index": c_idx,
                    "claim_text": claim_text,
                    "stored_verdict": stored_c["verdict"],
                    "replayed_verdict": assessment.verdict,
                    "stored_scores": stored_c["scores"],
                    "replayed_scores": vars(assessment.scores),
                })

            # Check exact_verdict
            if assessment.exact_verdict != stored_c["exact_verdict"]:
                exact_mismatches.append({
                    "answer_id": tid,
                    "claim_index": c_idx,
                    "claim_text": claim_text,
                    "stored_exact": stored_c["exact_verdict"],
                    "replayed_exact": assessment.exact_verdict,
                })

            # Check scores
            de = abs(assessment.scores.entailment - stored_c["scores"]["entailment"])
            dn = abs(assessment.scores.neutral - stored_c["scores"]["neutral"])
            dc = abs(assessment.scores.contradiction - stored_c["scores"]["contradiction"])
            diff = max(de, dn, dc)
            if diff > max_score_diff:
                max_score_diff = diff

            re_claims.append({
                "text": claim_text,
                "verdict": assessment.verdict,
                "exact_verdict": assessment.exact_verdict,
                "scores": vars(assessment.scores),
            })

        replayed_traces.append({
            "id": tid,
            "group": item["group"],
            "task": item["task"],
            "quality": item["quality"],
            "gold_spans": item["gold_spans"],
            "claims": re_claims,
            "inference_seconds": stored.get("inference_seconds", 0.0),
        })

    # a) Claim comparison report
    print("\n" + "=" * 70)
    print("A) CLAIM COMPARISON REPORT:")
    print("=" * 70)
    print(f"Claims compared (expected 6,375) : {total_claims}")
    print(f"Verdict mismatches               : {len(verdict_mismatches)}")
    print(f"Exact verdict mismatches         : {len(exact_mismatches)}")
    print(f"Max score difference vs traces   : {max_score_diff:.8f}")

    if verdict_mismatches:
        print("\nVERDICT MISMATCHES DETECTED:")
        for m in verdict_mismatches:
            print(json.dumps(m, indent=2))

    if exact_mismatches:
        print("\nEXACT VERDICT MISMATCHES DETECTED:")
        for m in exact_mismatches:
            print(json.dumps(m, indent=2))

    # b) Metrics report using exact v5 calibration function (score_policy & metrics)
    print("\n" + "=" * 70)
    print("B) BASELINE REPLAY METRICS (using score_policy & metrics from run_guard_calibration):")
    print("=" * 70)
    replayed_by_id = {str(t["id"]): t for t in replayed_traces}
    eval_rows = [score_policy(item, replayed_by_id[item["id"]], BASELINE) for item in dev_items.values()]
    base_metrics = metrics(eval_rows, include_subgroups=False)

    clean_altered = base_metrics["false_alterations"]
    clean_total = base_metrics["clean"]
    err_intercepted = base_metrics["fully_intercepted"]
    err_total = base_metrics["erroneous"]
    char_prec = base_metrics["character_precision"]

    print(f"Clean answers altered     : {clean_altered}/{clean_total} ({base_metrics['false_alteration_rate']*100:.2f}%)")
    print(f"Erroneous intercepted    : {err_intercepted}/{err_total} ({base_metrics['fully_intercepted_rate']*100:.2f}%)")
    print(f"Character precision       : {char_prec:.4f} ({char_prec*100:.2f}%)")

    # c) Interception by label type
    print("\n" + "=" * 70)
    print("C) INTERCEPTION BY LABEL TYPE:")
    print("=" * 70)
    label_totals = defaultdict(int)
    label_intercepted = defaultdict(int)

    for item in dev_items.values():
        tid = str(item["id"])
        labels = rag_labels_by_id.get(tid, [])
        if not labels:
            continue
        trace_row = replayed_by_id[tid]
        answer = item["answer"]
        final = answer
        claims = []
        for claim in trace_row["claims"]:
            altered = should_alter(claim["verdict"], SimpleNamespace(**claim["scores"]), claim["exact_verdict"], BASELINE)
            claims.append(dict(text=claim["text"], verdict=claim["verdict"], altered=altered))
            if altered:
                final = final.replace(claim["text"], "[FLAG_TEXT]")
        result = dict(final_answer=final, claims=claims)
        mask = removal_mask(answer, result)

        for lbl in labels:
            l_type = lbl["label_type"]
            span_set = set(range(lbl["start"], lbl["end"]))
            label_totals[l_type] += 1
            if span_set <= mask:
                label_intercepted[l_type] += 1

    for l_type in sorted(label_totals.keys()):
        tot = label_totals[l_type]
        inc = label_intercepted[l_type]
        print(f"  {l_type:<25} : {inc}/{tot} ({inc/tot*100:.1f}%)")

    # PASS validation check
    pass_claims = (total_claims == 6375 and len(verdict_mismatches) == 0 and len(exact_mismatches) == 0)
    pass_clean = (clean_altered == 386 and clean_total == 399)
    pass_err = (err_intercepted == 239 and err_total == 321)
    pass_prec = abs(char_prec - 0.0729365) < 0.0001

    overall_pass = pass_claims and pass_clean and pass_err and pass_prec

    print("\n" + "=" * 70)
    print(f"GATE VERDICT: {'PASS' if overall_pass else 'FAIL'}")
    print("=" * 70)
    print(f"  0 verdict mismatches       : {'PASS' if len(verdict_mismatches) == 0 else 'FAIL'}")
    print(f"  Clean altered = 386/399    : {'PASS' if pass_clean else 'FAIL'}")
    print(f"  Erroneous int = 239/321    : {'PASS' if pass_err else 'FAIL'}")
    print(f"  Char precision = 0.0729    : {'PASS' if pass_prec else 'FAIL'}")

    return overall_pass


if __name__ == "__main__":
    passed = run_baseline_replay_gate()
    sys.exit(0 if passed else 1)
