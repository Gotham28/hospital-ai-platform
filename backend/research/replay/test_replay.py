"""Unit test for CachedScorer replay harness on 10 development answers."""

from __future__ import annotations

import json
from pathlib import Path
import random
import sys

from backend.research.guard.guard import _thresholds
from backend.research.replay.cache import NLICache
from backend.research.replay.scorer import CachedScorer
from backend.research.run_guard_calibration import load_inputs, selected_items


def test_replay_10_answers(seed: int = 20261028) -> None:
    print(f"Loading inputs and development traces for 10-answer replay test (seed={seed})...")
    manifest, responses = load_inputs()
    dev_items = {item["id"]: item for item in selected_items(manifest, responses, "development")}
    traces = [json.loads(line) for line in Path("backend/research/results/guard-parser-v5-2026-10-28/development-v5-traces.jsonl").read_text(encoding="utf-8").splitlines()]

    random.seed(seed)
    sampled_traces = random.sample(traces, 10)
    print(f"Sampled 10 answers: {[t['id'] for t in sampled_traces]}")

    test_cache_path = Path("backend/research/replay/test_cache_10.jsonl")
    if test_cache_path.exists():
        test_cache_path.unlink()

    # Step 1: Fill cache using CachedScorer in 'fill' mode
    print("\n--- Phase 1: Fill cache using CachedScorer(mode='fill') ---")
    fill_cache = NLICache(test_cache_path, flush_every=10)
    fill_scorer = CachedScorer(fill_cache, mode="fill", batch_size=16, device="cpu")
    _, thresholds = _thresholds("en")

    total_claims = 0
    for t in sampled_traces:
        item = dev_items[str(t["id"])]
        for c in t["claims"]:
            total_claims += 1
            fill_scorer.assess(
                c["text"],
                item["context"],
                entailment_threshold=thresholds.entailment,
                contradiction_threshold=thresholds.contradiction,
            )

    fill_cache.flush()
    fill_cache.close()
    print(f"Phase 1 complete: evaluated {total_claims} claims across 10 answers. Cache entries: {len(fill_cache)}")

    # Step 2: Run claim assessment path through CachedScorer in 'strict' mode
    print("\n--- Phase 2: Run CachedScorer(mode='strict') and verify parity ---")
    strict_cache = NLICache(test_cache_path)
    strict_scorer = CachedScorer(strict_cache, mode="strict")
    assert strict_scorer._model is None, "Strict mode must not load model weights!"

    mismatches = []
    comparisons = 0
    max_score_diff = 0.0

    for t in sampled_traces:
        tid = str(t["id"])
        item = dev_items[tid]
        for c_idx, stored in enumerate(t["claims"]):
            comparisons += 1
            re_assessment = strict_scorer.assess(
                stored["text"],
                item["context"],
                entailment_threshold=thresholds.entailment,
                contradiction_threshold=thresholds.contradiction,
            )

            # Check verdicts
            v_match = (re_assessment.verdict == stored["verdict"])
            ev_match = (re_assessment.exact_verdict == stored["exact_verdict"])

            # Check scores with tolerance 1e-4
            de = abs(re_assessment.scores.entailment - stored["scores"]["entailment"])
            dn = abs(re_assessment.scores.neutral - stored["scores"]["neutral"])
            dc = abs(re_assessment.scores.contradiction - stored["scores"]["contradiction"])
            diff = max(de, dn, dc)
            if diff > max_score_diff:
                max_score_diff = diff

            score_match = (diff <= 1e-4)

            if not (v_match and ev_match and score_match):
                mismatch_info = {
                    "answer_id": tid,
                    "claim_index": c_idx,
                    "claim_text": stored["text"],
                    "stored_verdict": stored["verdict"],
                    "re_verdict": re_assessment.verdict,
                    "stored_exact": stored["exact_verdict"],
                    "re_exact": re_assessment.exact_verdict,
                    "stored_scores": stored["scores"],
                    "re_scores": vars(re_assessment.scores),
                    "max_diff": diff,
                }
                mismatches.append(mismatch_info)

    print("\n" + "="*70)
    print("REPLAY TEST RESULTS (10 answers, strict mode):")
    print("="*70)
    print(f"Total claims evaluated     : {comparisons}")
    print(f"Total mismatches           : {len(mismatches)}")
    print(f"Max score difference vs v5 : {max_score_diff:.8f} (tolerance: 1e-4)")

    if mismatches:
        print("\nMISMATCH DETAILS:")
        for m in mismatches:
            print(json.dumps(m, indent=2))
        sys.exit(1)
    else:
        print("PASS: Exact match on all verdicts, exact_verdicts, and scores <= 1e-4!")

    # Clean up test cache
    if test_cache_path.exists():
        test_cache_path.unlink()
        print("Cleaned up temporary test cache.")


if __name__ == "__main__":
    test_replay_10_answers()
