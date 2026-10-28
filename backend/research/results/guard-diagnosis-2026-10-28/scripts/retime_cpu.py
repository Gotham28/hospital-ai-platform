import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(".").resolve()))

import torch
from backend.research.guard.nli import MultilingualNLIScorer, _decompose_passages, _select_candidate_passages
from backend.research.run_guard_calibration import load_inputs, selected_items

# 1. Determine physical cores
physical_cores = 4
torch.set_num_threads(physical_cores)
print(f"Set torch.set_num_threads({physical_cores}) (physical cores = {physical_cores})")

# 2. Gather candidate pairs from development traces
manifest, responses = load_inputs()
dev_items = {item["id"]: item for item in selected_items(manifest, responses, "development")}
traces = [json.loads(line) for line in Path("backend/research/results/guard-parser-v5-2026-10-28/development-v5-traces.jsonl").read_text(encoding="utf-8").splitlines()]

all_pairs = []
for t in traces:
    tid = t["id"]
    item = dev_items[tid]
    decomposed = _decompose_passages(item["context"])
    for c in t["claims"]:
        claim_text = c["text"]
        candidates = _select_candidate_passages(claim_text, decomposed, max_candidates=4)
        if len(candidates) >= 2:
            for cand in candidates:
                all_pairs.append((cand, claim_text))
        if len(all_pairs) >= 500:
            break
    if len(all_pairs) >= 500:
        break

# Sort pairs by total character length (passage + claim)
all_pairs.sort(key=lambda p: len(p[0]) + len(p[1]))
print(f"Collected {len(all_pairs)} candidate pairs, sorted by length.")

TOTAL_TARGET_PAIRS = 24338

# Test for each batch size: 8, 16, 32
results = {}
for bs in [8, 16, 32]:
    n_pairs = bs * 3
    test_pairs = all_pairs[:n_pairs]
    
    scorer = MultilingualNLIScorer(device="cpu", batch_size=bs)
    
    # Warm-up batch (1 batch of size bs)
    warmup_batch = test_pairs[:bs]
    scorer.score_pairs(warmup_batch)
    
    # Time 3 batches of size bs
    t0 = time.perf_counter()
    scores = scorer.score_pairs(test_pairs)
    t1 = time.perf_counter()
    
    elapsed = t1 - t0
    s_per_pair = elapsed / n_pairs
    proj_sec = TOTAL_TARGET_PAIRS * s_per_pair
    proj_min = proj_sec / 60.0
    proj_hrs = proj_min / 60.0
    
    results[bs] = {
        "elapsed_3_batches": elapsed,
        "n_pairs": n_pairs,
        "s_per_pair": s_per_pair,
        "projected_sec": proj_sec,
        "projected_min": proj_min,
        "projected_hrs": proj_hrs,
    }
    print(f"\n--- Batch Size {bs} (3 batches = {n_pairs} pairs) ---")
    print(f"  Elapsed (3 batches): {elapsed:.4f} s")
    print(f"  Seconds per pair   : {s_per_pair:.4f} s/pair")
    print(f"  Projected (24,338) : {proj_sec:.1f} s | {proj_min:.2f} min | {proj_hrs:.2f} hours")

print("\n" + "="*80)
print(f"{'Batch Size':<12} | {'s/pair':<12} | {'Projected Total (24,338 pairs)':<35}")
print("="*80)
for bs, res in results.items():
    print(f"{bs:<12} | {res['s_per_pair']:.4f} s    | {res['projected_min']:.1f} min ({res['projected_hrs']:.2f} hours)")
