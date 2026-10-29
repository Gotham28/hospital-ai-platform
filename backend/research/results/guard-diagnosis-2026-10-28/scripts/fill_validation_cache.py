"""Fill validation NLI cache for baseline and current HEAD (Fix 3) replay."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time

repo_root = Path("c:/Users/Sreehari/.gemini/antigravity/scratch/hospital-ai-platform")
sys.path.insert(0, str(repo_root))

import torch
from backend.research.guard.claims import split_claims
import backend.research.guard.claims as c_mod
from backend.research.guard.nli import MultilingualNLIScorer, _decompose_passages, _select_candidate_passages
from backend.research.replay.cache import DEFAULT_MODEL_REVISION, NLICache, make_key
from backend.research.run_guard_calibration import load_inputs, selected_items

CACHE_PATH = repo_root / "backend/research/results/guard-diagnosis-2026-10-28/nli_cache_validation.jsonl"


def enumerate_validation_pairs():
    manifest, responses = load_inputs()
    val_items = {item["id"]: item for item in selected_items(manifest, responses, "validation")}

    unique_pairs = {}

    # 1. Baseline pairs (pre-Fix 3 claims + standard decompose)
    orig_pats = c_mod._NON_CLAIM_PATTERNS
    orig_non_fac = set(c_mod._NON_FACTUAL)
    c_mod._NON_CLAIM_PATTERNS = ()
    if "sure" in c_mod._NON_FACTUAL:
        c_mod._NON_FACTUAL.remove("sure")

    for tid, item in val_items.items():
        passages = _decompose_passages(item["context"])
        claims = split_claims(item["answer"], lang=item["lang"])
        for c_idx, c in enumerate(claims):
            candidates = _select_candidate_passages(c, passages, max_candidates=4)
            for p_idx, p in enumerate(candidates):
                k = make_key(p, c)
                if k not in unique_pairs:
                    unique_pairs[k] = {
                        "key": k,
                        "passage": p,
                        "claim": c,
                        "answer_id": str(tid),
                        "claim_index": c_idx,
                        "passage_index": p_idx,
                    }

    # Restore Fix 3 claims settings
    c_mod._NON_CLAIM_PATTERNS = orig_pats
    c_mod._NON_FACTUAL = orig_non_fac

    # 2. HEAD pairs (Fix 3 claims + standard decompose)
    for tid, item in val_items.items():
        passages = _decompose_passages(item["context"])
        claims = split_claims(item["answer"], lang=item["lang"])
        for c_idx, c in enumerate(claims):
            candidates = _select_candidate_passages(c, passages, max_candidates=4)
            for p_idx, p in enumerate(candidates):
                k = make_key(p, c)
                if k not in unique_pairs:
                    unique_pairs[k] = {
                        "key": k,
                        "passage": p,
                        "claim": c,
                        "answer_id": str(tid),
                        "claim_index": c_idx,
                        "passage_index": p_idx,
                    }

    return unique_pairs


def main():
    num_threads = 4
    batch_size = 16
    flush_every = 16
    log_every = 200

    torch.set_num_threads(num_threads)
    print(f"Configured torch.set_num_threads({num_threads})")

    print("Enumerating validation split pairs for Baseline and HEAD...")
    unique_pairs = enumerate_validation_pairs()
    total_unique = len(unique_pairs)
    print(f"Total unique validation pairs: {total_unique}")

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    cache = NLICache(CACHE_PATH, flush_every=flush_every)
    existing_count = len(cache)
    print(f"Existing validation cache records: {existing_count}")

    remaining = [v for k, v in unique_pairs.items() if k not in cache]
    print(f"Remaining pairs to score: {len(remaining)}")

    if not remaining:
        print("Validation cache is already fully populated!")
        return

    # Sort remaining by length for padding efficiency
    remaining.sort(key=lambda x: len(x["passage"]) + len(x["claim"]))

    print(f"Initializing MultilingualNLIScorer on CPU (batch_size={batch_size})...")
    scorer = MultilingualNLIScorer(device="cpu", batch_size=batch_size)

    print(f"Starting validation cache fill ({len(remaining)} pairs)...")
    start_time = time.perf_counter()
    processed_count = 0

    for i in range(0, len(remaining), batch_size):
        chunk = remaining[i : i + batch_size]
        pairs_to_score = [(item["passage"], item["claim"]) for item in chunk]
        scores_list = scorer.score_pairs(pairs_to_score)

        for item, scores in zip(chunk, scores_list):
            cache.set(
                item["key"],
                scores,
                answer_id=item["answer_id"],
                claim_index=item["claim_index"],
                passage_index=item["passage_index"],
            )

        processed_count += len(chunk)

        if processed_count % log_every < batch_size or processed_count == len(remaining):
            elapsed = time.perf_counter() - start_time
            rate = processed_count / elapsed if elapsed > 0 else 0
            eta_sec = (len(remaining) - processed_count) / rate if rate > 0 else 0
            print(
                f"[{time.strftime('%H:%M:%S')}] Validation Progress: {processed_count}/{len(remaining)} pairs "
                f"({processed_count / len(remaining) * 100:.1f}%) | "
                f"Cache line count: {len(cache)} | "
                f"Elapsed: {elapsed:.1f}s ({elapsed / 60:.1f}m) | "
                f"Rate: {rate:.2f} pairs/s | "
                f"ETA [PROJECTION]: {eta_sec / 60:.1f}m",
                flush=True,
            )

    cache.flush()
    total_elapsed = time.perf_counter() - start_time
    print(f"Validation cache fill complete in {total_elapsed:.1f}s ({total_elapsed / 60:.1f}m). Total entries: {len(cache)}")


if __name__ == "__main__":
    main()
