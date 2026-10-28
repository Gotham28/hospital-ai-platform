import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))

import json
from backend.research.run_guard_calibration import load_inputs, selected_items
from backend.research.guard.nli import MultilingualNLIScorer, _decompose_passages, _select_candidate_passages

manifest, responses = load_inputs()
dev_items = {item["id"]: item for item in selected_items(manifest, responses, "development")}

traces = [json.loads(line) for line in Path("backend/research/results/guard-parser-v5-2026-10-28/development-v5-traces.jsonl").read_text(encoding="utf-8").splitlines()]

count_1 = 0
count_ge_2 = 0
passage_counts = {1: 0, 2: 0, 3: 0, 4: 0}
total_multi_passage_pairs = 0

sample_pairs = []

for t in traces:
    tid = t["id"]
    item = dev_items[tid]
    decomposed = _decompose_passages(item["context"])
    for c in t["claims"]:
        claim_text = c["text"]
        candidates = _select_candidate_passages(claim_text, decomposed, max_candidates=4)
        n_cand = len(candidates)
        if n_cand == 1:
            count_1 += 1
            passage_counts[1] += 1
        elif n_cand >= 2:
            count_ge_2 += 1
            passage_counts[n_cand] = passage_counts.get(n_cand, 0) + 1
            total_multi_passage_pairs += n_cand
            if len(sample_pairs) < 20:
                for cand in candidates:
                    if len(sample_pairs) < 20:
                        sample_pairs.append((cand, claim_text))

total_claims = count_1 + count_ge_2

print(f"Total claims evaluated: {total_claims}")
print(f"Claims with exactly 1 candidate passage: {count_1} ({count_1 / total_claims * 100:.2f}%)")
print(f"Claims with >= 2 candidate passages  : {count_ge_2} ({count_ge_2 / total_claims * 100:.2f}%)")
print(f"Breakdown by candidate passage count: {passage_counts}")
print(f"Total (passage, claim) pairs across multi-passage claims: {total_multi_passage_pairs}")

print(f"\nTiming CPU scoring on 20 (passage, claim) pairs...")
scorer = MultilingualNLIScorer(device="cpu", batch_size=8)

# Warmup 1 pair
scorer.score_pairs([sample_pairs[0]])

start_t = time.perf_counter()
scores = scorer.score_pairs(sample_pairs)
end_t = time.perf_counter()

elapsed = end_t - start_t
per_pair = elapsed / len(sample_pairs)
projected_multi_seconds = total_multi_passage_pairs * per_pair
projected_multi_minutes = projected_multi_seconds / 60.0
projected_multi_hours = projected_multi_minutes / 60.0

print(f"Time for 20 pairs: {elapsed:.4f} seconds ({per_pair:.4f} seconds/pair)")
print(f"Projected time for all {total_multi_passage_pairs} multi-passage pairs:")
print(f"  Projected seconds: {projected_multi_seconds:.1f}s")
print(f"  Projected minutes: {projected_multi_minutes:.2f} min")
print(f"  Projected hours  : {projected_multi_hours:.2f} hours")
